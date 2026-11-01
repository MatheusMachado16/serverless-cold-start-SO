#!/usr/bin/env bash
# Constrói as imagens locais do estudo. As imagens de execução do SeBS não existem no Docker Hub,
# então são construídas a partir do repositório do SeBS (no commit fixado por 01_preparar.sh).
# Uso: ./scripts/construir_imagens.sh [DIR_SEBS]     (padrão: ~/serverless-benchmarks)
#      REBUILD=1 ./scripts/construir_imagens.sh      (força reconstruir tudo)
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SEBS="${1:-$HOME/serverless-benchmarks}"
IMG_PY=spcleth/serverless-benchmarks:run.local.python.3.11
IMG_JS=spcleth/serverless-benchmarks:run.local.nodejs.20
BASE_JS=cs-sebs-node-base:orig      # imagem original do SeBS para Node, antes do patch de PATH
MINIO_FIXO=cs-minio:fixed           # a imagem oficial do Minio foi removida do Docker Hub

pronta() { [ -z "${REBUILD:-}" ] && docker image inspect "$1" >/dev/null 2>&1; }

[ -f "$SEBS/dockerfiles/local/python/Dockerfile.run" ] || {
  echo "SeBS não encontrado em $SEBS. Rode antes ./scripts/01_preparar.sh"; exit 1; }
cd "$SEBS"

echo "== Python 3.11"
if pronta "$IMG_PY"; then echo "  já existe: $IMG_PY"; else
  docker build -f dockerfiles/local/python/Dockerfile.run \
    --build-arg BASE_IMAGE=python:3.11-slim --build-arg VERSION=3.11 -t "$IMG_PY" .
fi

echo "== Node.js 20 (imagem original do SeBS)"
if pronta "$BASE_JS"; then echo "  já existe: $BASE_JS"; else
  docker build -f dockerfiles/local/nodejs/Dockerfile.run \
    --build-arg BASE_IMAGE=ubuntu:22.04 --build-arg VERSION=20 -t "$BASE_JS" .
fi

echo "== Node.js 20 com o patch de PATH/NODE_PATH (configs/patches/nodejs-path.Dockerfile)"
docker build -t "$IMG_JS" -f "$RAIZ/configs/patches/nodejs-path.Dockerfile" "$RAIZ/configs/patches"

echo "== Minio"
if pronta "$MINIO_FIXO"; then echo "  já existe: $MINIO_FIXO"; else
  docker pull cgr.dev/chainguard/minio:latest
  docker tag cgr.dev/chainguard/minio:latest "$MINIO_FIXO"
fi

echo "Imagens prontas. Registre os identificadores em docs/ambiente.md:"
docker images --digests --format '  {{.Repository}}:{{.Tag}}  {{.ID}}' | grep -E "serverless-benchmarks|cs-sebs-node-base|cs-minio" || true