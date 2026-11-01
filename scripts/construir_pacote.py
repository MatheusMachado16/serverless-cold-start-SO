#!/usr/bin/env python3
"""Monta o pacote de uma aplicação no layout que o SeBS local espera em /function.

  pacotes/<workload>/<runtime>/<pacote>/
      function/            function.py|js + wrappers (storage/nosql) + arquivos da aplicação
      .python_packages/lib/site-packages/   (Python)   |   node_modules/   (Node.js)

Replica `package_code` de sebs/local/local.py sem exigir a instalação completa do SeBS.
As dependências Python são resolvidas para a versão do Python da IMAGEM (não a do host).

  ./scripts/construir_pacote.py --workload CTRL --runtime python --pacote padrao
  ./scripts/construir_pacote.py --workload A2 --runtime python --pacote ampliado --extra-mib 50 --extra-arquivos 200

Pacotes (decisão final no piloto; ver docs/protocolo.md, item 5):
  minimo    só o wrapper necessário à aplicação (A1: nosql; A2: storage) + dependências
  padrao    como o SeBS: ambos os wrappers e as dependências do módulo
  ampliado  padrao + arquivos EXTRAS apenas PRESENTES (não importados): aumenta bytes, não trabalho
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BENCH = {"CTRL": "000.microbenchmarks/010.sleep", "A1": "100.webapps/130.crud-api",
         "A2": "200.multimedia/210.thumbnailer"}
WRAPPER_NECESSARIO = {"CTRL": [], "A1": ["nosql"], "A2": ["storage"]}
# Python: o `minio` já vem na imagem run.local.python (pip install no Dockerfile.run); só o nosql traz boto3.
DEPS_MODULO_PY = {"nosql": ["boto3==1.28.3"], "storage": []}
DEPS_MODULO_JS = {"nosql": {"aws-sdk": "2.1692.0"}, "storage": {"minio": "7.0.16"}}
# configs/systems.json do SeBS: o pacote Node local sempre inclui estes (o "padrão" os replica)
PACOTES_PADRAO_JS = {"aws-sdk": "2.1692.0", "minio": "7.0.16"}


def sh(cmd, **kw):
    print("  $", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True, **kw)


def copiar_aplicacao(origem: Path, destino_fn: Path):
    destino_fn.mkdir(parents=True, exist_ok=True)
    for f in origem.iterdir():
        if f.is_file() and not f.name.startswith("requirements.txt.") and not f.name.startswith("package.json."):
            if f.name not in ("requirements.txt", "package.json"):
                shutil.copy2(f, destino_fn / f.name)


def construir_python(a, bench: Path, sebs: Path, saida: Path):
    fn = saida / "function"
    copiar_aplicacao(bench / "python", fn)
    wrappers = ["storage", "nosql"] if a.pacote != "minimo" else WRAPPER_NECESSARIO[a.workload]
    for w in wrappers:
        shutil.copy2(sebs / f"benchmarks/wrappers/local/python/{w}.py", fn / f"{w}.py")
    deps = []
    req = bench / "python" / f"requirements.txt.{a.versao}"
    req = req if req.exists() else bench / "python" / "requirements.txt"
    if req.exists():
        deps += [l.strip() for l in req.read_text().splitlines() if l.strip() and not l.startswith("#")]
    for w in WRAPPER_NECESSARIO[a.workload]:
        deps += DEPS_MODULO_PY[w]
    if deps:
        alvo = saida / ".python_packages/lib/site-packages"
        alvo.mkdir(parents=True, exist_ok=True)
        sh([sys.executable, "-m", "pip", "install", "--quiet", "--target", str(alvo), "--no-cache-dir",
            "--only-binary=:all:", "--python-version", a.versao, "--platform", "manylinux2014_x86_64",
            "--implementation", "cp", *deps])
    return deps


def npm_install_em_conteiner(saida: Path):
    """npm install dentro da imagem de execução (glibc do runtime). Módulos nativos como o `sharp`
    compilados no host (glibc nova do Bluefin) não carregam no contêiner (Ubuntu 22.04)."""
    import os
    img = os.environ.get("CS_IMAGEM_NODE", "spcleth/serverless-benchmarks:run.local.nodejs.20")
    cmd = ("apt-get update -qq && apt-get install -y -qq --no-install-recommends build-essential >/dev/null "
           "&& rm -rf node_modules && npm install --omit=dev --no-audit --no-fund --silent; rc=$?; "
           f"chown -R {os.getuid()}:{os.getgid()} /function; exit $rc")
    sh(["docker", "run", "--rm", "--user", "root", "-e", "HOME=/tmp", "-v", f"{saida.resolve()}:/function",
        "-w", "/function", "--entrypoint", "bash", img, "-c", cmd])


def construir_node(a, bench: Path, sebs: Path, saida: Path):
    fn = saida / "function"
    copiar_aplicacao(bench / "nodejs", fn)
    wrappers = ["storage", "nosql"] if a.pacote != "minimo" else WRAPPER_NECESSARIO[a.workload]
    for w in wrappers:
        shutil.copy2(sebs / f"benchmarks/wrappers/local/nodejs/{w}.js", fn / f"{w}.js")
    pj_origem = bench / "nodejs" / "package.json"
    pj = json.loads(pj_origem.read_text()) if pj_origem.exists() else {"name": "function", "version": "1.0.0"}
    pj.setdefault("dependencies", {})
    if a.pacote != "minimo":
        pj["dependencies"].update(PACOTES_PADRAO_JS)
    for w in WRAPPER_NECESSARIO[a.workload]:
        pj["dependencies"].update(DEPS_MODULO_JS[w])
    (saida / "package.json").write_text(json.dumps(pj, indent=2))
    if pj["dependencies"]:
        npm_install_em_conteiner(saida)
    return pj["dependencies"]


def adicionar_extras(saida: Path, mib: int, n: int):
    """Arquivos determinísticos, apenas presentes (nunca importados)."""
    alvo = saida / "function" / "extras"
    alvo.mkdir(parents=True, exist_ok=True)
    por_arquivo = max(1, mib * 1024 * 1024 // n)
    bloco = hashlib.sha256(b"cold-start-so").digest() * 1024  # 32 KiB
    for i in range(n):
        dados = (bloco * (por_arquivo // len(bloco) + 1))[:por_arquivo]
        (alvo / f"extra_{i:04d}.bin").write_bytes(dados)


def estatisticas(saida: Path) -> dict:
    arqs = [p for p in saida.rglob("*") if p.is_file()]
    return {"n_arquivos": len(arqs), "bytes": sum(p.stat().st_size for p in arqs)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workload", required=True, choices=BENCH)
    ap.add_argument("--runtime", required=True, choices=["python", "nodejs"])
    ap.add_argument("--pacote", default="padrao", choices=["minimo", "padrao", "ampliado"])
    ap.add_argument("--versao", default=None, help="Python da imagem (padrão 3.11) ")
    ap.add_argument("--sebs-dir", default="~/serverless-benchmarks")
    ap.add_argument("--extra-mib", type=int, default=50)
    ap.add_argument("--extra-arquivos", type=int, default=200)
    ap.add_argument("--saida-base", default=str(RAIZ / "pacotes"))
    a = ap.parse_args()
    a.versao = a.versao or "3.11"
    sebs = Path(a.sebs_dir).expanduser()
    bench = RAIZ / "benchmarks" / BENCH[a.workload]
    saida = Path(a.saida_base) / a.workload / a.runtime / a.pacote
    if saida.exists():
        shutil.rmtree(saida)
    saida.mkdir(parents=True)
    print(f"Construindo {a.workload}/{a.runtime}/{a.pacote} em {saida}")
    deps = construir_python(a, bench, sebs, saida) if a.runtime == "python" else construir_node(a, bench, sebs, saida)
    if a.pacote == "ampliado":
        adicionar_extras(saida, a.extra_mib, a.extra_arquivos)
    info = {"workload": a.workload, "runtime": a.runtime, "pacote": a.pacote, "dependencias": deps,
            "extras_mib": a.extra_mib if a.pacote == "ampliado" else 0, **estatisticas(saida)}
    (saida / "pacote_info.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
