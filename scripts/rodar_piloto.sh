#!/usr/bin/env bash
# Piloto automatizado: verificação -> serviços -> semeadura -> 26 configs x 5 frios -> análise.
# Uso: ./scripts/rodar_piloto.sh [--sem-servicos]
#   (E4 'descartado' precisa de root: use `sudo -E ./scripts/rodar_piloto.sh` ou libere `sudo -n`.)
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"; cd "$RAIZ"
./scripts/00_verificar_host.sh || true
if [ "${1:-}" != "--sem-servicos" ]; then
  ./scripts/servicos.sh up
  python3 scripts/semear_servicos.py
fi
# garante que o piloto comece com tudo o que será usado pronto
python3 orquestrador/run_experimento.py --piloto --rodada 0 --eventos
python3 analise/analisar.py --saida piloto
echo "Piloto concluído. Veja analise/saida/diagnostico_piloto.md e as figuras fig_piloto_*.png"
