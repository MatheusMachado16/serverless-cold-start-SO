#!/usr/bin/env bash
# Prepara tudo o que fica FORA da medição: SeBS no commit fixado, imagens, pacotes e dependências do host.
# Uso: ./scripts/01_preparar.sh [DIR_SEBS]    (padrão: ~/serverless-benchmarks)
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SEBS="${1:-$HOME/serverless-benchmarks}"
COMMIT=b37f475542436ffb6b0ad03bd5972a680ecb8186
IMG_PY=spcleth/serverless-benchmarks:run.local.python.3.11
IMG_JS=spcleth/serverless-benchmarks:run.local.nodejs.20

echo "== 1. SeBS no commit $COMMIT"
[ -d "$SEBS/.git" ] || git clone https://github.com/spcl/serverless-benchmarks "$SEBS"
git -C "$SEBS" checkout -q "$COMMIT"
git -C "$SEBS" rev-parse HEAD
# o orquestrador e os scripts leem benchmarks/ na raiz do repo: link para o SeBS (não versionado)
if [ -e "$RAIZ/benchmarks" ] && [ ! -L "$RAIZ/benchmarks" ]; then echo "  aviso: benchmarks/ já existe como pasta; mantida"
else ln -sfn "$SEBS/benchmarks" "$RAIZ/benchmarks"; fi

echo "== 2. Dependências Python do host (orquestrador, análise, semeadura)"
python3 -m pip install --user --break-system-packages -r "$RAIZ/requirements.txt"

echo "== 3. Imagens (construção e download fora da medição)"
"$RAIZ/scripts/construir_imagens.sh" "$SEBS"   # imagens do SeBS (não estão no Docker Hub), patch do Node e Minio
docker pull "scylladb/scylla:${SCYLLA_VERSION:-6.2}"

echo "== 4. Pacotes das aplicações"
for rt in python nodejs; do
  for w in A1 A2; do
    for p in padrao; do python3 "$RAIZ/scripts/construir_pacote.py" --workload $w --runtime $rt --pacote $p --sebs-dir "$SEBS" >/dev/null; done
  done
  python3 "$RAIZ/scripts/construir_pacote.py" --workload CTRL --runtime $rt --pacote padrao --sebs-dir "$SEBS" >/dev/null
done
# E2 (A2): mínimo e ampliado
for rt in python nodejs; do
  for p in minimo ampliado; do python3 "$RAIZ/scripts/construir_pacote.py" --workload A2 --runtime $rt --pacote $p --sebs-dir "$SEBS" >/dev/null; done
done
python3 - <<PY
import json, pathlib
p = pathlib.Path("$RAIZ/configs/ambiente_local.json"); d = json.loads(p.read_text())
d["sebs_dir"] = "$SEBS" if "${1:-}" else d["sebs_dir"]; p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
PY
echo "Pacotes:"; for f in "$RAIZ"/pacotes/*/*/*/pacote_info.json; do python3 -c "import json,sys;d=json.load(open('$f'));print(f\"  {d['workload']}/{d['runtime']}/{d['pacote']}: {d['n_arquivos']} arquivos, {d['bytes']/1e6:.1f} MB\")"; done
echo "Pronto. Próximo: ./scripts/servicos.sh up && python3 scripts/semear_servicos.py"