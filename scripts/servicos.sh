#!/usr/bin/env bash
# Sobe/derruba os serviços auxiliares (fora da medição). Uso: ./scripts/servicos.sh up|down|status
set -euo pipefail
SCYLLA_IMG="scylladb/scylla:${SCYLLA_VERSION:-6.2}"
case "${1:-status}" in
 up)
  docker rm -f cs-scylla cs-minio >/dev/null 2>&1 || true
  docker run -d --name cs-scylla --hostname cs-scylla "$SCYLLA_IMG" \
     --smp 1 --memory 1G --overprovisioned 1 --alternator-port 8000 --alternator-write-isolation=only_rmw_uses_lwt >/dev/null
  docker run -d --name cs-minio -e MINIO_ROOT_USER=coldstart -e MINIO_ROOT_PASSWORD=coldstart-secret \
     -e MINIO_ACCESS_KEY=coldstart -e MINIO_SECRET_KEY=coldstart-secret cs-minio:fixed server /data >/dev/null
  echo "aguardando serviços..."
  for i in $(seq 1 90); do
    IP_S=$(docker inspect -f '{{.NetworkSettings.Networks.bridge.IPAddress}}' cs-scylla); IP_M=$(docker inspect -f '{{.NetworkSettings.Networks.bridge.IPAddress}}' cs-minio)
    if curl -s -o /dev/null "http://$IP_S:8000/" && curl -s -o /dev/null "http://$IP_M:9000/minio/health/live"; then
      echo "ScyllaDB (Alternator): $IP_S:8000 | Minio: $IP_M:9000"; exit 0; fi
    sleep 2
  done; echo "tempo esgotado esperando os serviços"; docker logs --tail 20 cs-scylla; exit 1;;
 down) docker rm -f cs-scylla cs-minio;;
 status) docker ps --filter name=cs-scylla --filter name=cs-minio;;
esac
