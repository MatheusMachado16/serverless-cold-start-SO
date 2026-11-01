#!/usr/bin/env bash
# Coleta as informações para docs/ambiente.md e confere pré-requisitos do host.
# Uso: ./scripts/00_verificar_host.sh   (gera docs/ambiente_coletado.txt)
set -u
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$RAIZ/docs/ambiente_coletado.txt"
ok(){ printf '  [ok]   %s\n' "$1"; }; aviso(){ printf '  [ATENÇÃO] %s\n' "$1"; }
{
echo "# coletado em $(date -Is)"
echo "## SO";        lsb_release -ds 2>/dev/null; uname -r
echo "## CPU";       lscpu | grep -E 'Model name|^CPU\(s\)|Thread|Core'
echo "## Memória";   free -h; echo "swap:"; swapon --show
echo "## Governador/driver"; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver 2>&1
echo "## Docker";    docker version --format 'server={{.Server.Version}}' 2>&1
docker info --format 'storage_driver={{.Driver}} cgroup={{.CgroupVersion}}/{{.CgroupDriver}} runtime={{.DefaultRuntime}}' 2>&1
findmnt -no FSTYPE,SOURCE /var/lib/docker 2>&1
echo "## Ferramentas"; python3 --version; strace -V 2>&1 | head -1; perf --version 2>&1; node --version 2>&1
echo "## Imagens";   docker images --digests 2>&1 | grep -E 'serverless|scylla|minio' 
echo "## perf_event_paranoid"; cat /proc/sys/kernel/perf_event_paranoid
} > "$OUT" 2>&1
echo "Informações salvas em $OUT (copie os valores para docs/ambiente.md)"; echo
echo "Verificações:"
command -v docker >/dev/null && docker ps >/dev/null 2>&1 && ok "docker acessível" || aviso "docker indisponível para este usuário"
[ "$(stat -fc %T /sys/fs/cgroup)" = "cgroup2fs" ] && ok "cgroups v2" || aviso "cgroups v1: ler_cgroup() não encontrará os arquivos"
sudo -n true 2>/dev/null && ok "sudo sem senha (necessário p/ drop_caches em E4)" || aviso "sudo -n falha: E4 'descartado' exigirá rodar o orquestrador como root"
command -v strace >/dev/null && ok "strace" || aviso "strace ausente (sudo apt install strace)"
command -v perf   >/dev/null && ok "perf"   || aviso "perf ausente (sudo apt install linux-tools-generic)"
[ "$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)" = "performance" ] && ok "governador performance" || aviso "governador != performance (sudo cpupower frequency-set -g performance)"
[ -n "$(swapon --show --noheadings)" ] && aviso "há swap ativo no host; defina a política e registre em docs/ambiente.md" || ok "sem swap no host"
for p in /sys/class/hwmon/hwmon*/name; do grep -qE 'k10temp|coretemp' "$p" 2>/dev/null && ok "sensor de temperatura" && break; done
[ -r /sys/fs/cgroup/memory.peak ] || aviso "memory.peak não está na raiz do cgroup (normal); conferir dentro do cgroup do contêiner no piloto"
