#!/usr/bin/env python3
"""Executa uma rodada do experimento (README, seção 9).

Exemplos
  # ver a agenda sem executar nada
  ./run_experimento.py --configs configs/e1_runtime_memoria.json --n-frio 5 --dry-run
  # piloto: 5 frios por configuração (todas as 26), 10 quentes
  ./run_experimento.py --piloto --rodada 0
  # validar o pipeline em máquina SEM Docker (não é cold start de contêiner!)
  ./run_experimento.py --configs configs/smoke.json --backend processo --n-frio 30 --n-quente 20 --tag smoke
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletores  # noqa: E402
import medir  # noqa: E402
from backends import BACKENDS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

COLUNAS = [
    # identificação
    "amostra_id", "exp", "config_id", "rodada", "repeticao", "ordem", "seed", "tag",
    # aplicação e parâmetros
    "workload", "runtime", "pacote", "mem_mib", "mem_bytes", "rede", "cache", "backend",
    # execução
    "tipo", "container_id", "t0_wall_ns", "porta",
    "t_created_ms", "t_started_ms", "t_ready_ms", "gap_ready_req_ms", "t_req_cold_ms", "t_cold_total_ms",
    "lat_req_ms", "srv_import_ms", "sondagens", "intervalo_sondagem_ms", "http_status",
    "ev_create_ms", "ev_start_ms", "ev_die_ms", "ev_oom_ms",
    "cache_prep_s", "cache_nivel",
    # observação (cgroup/proc)
    "cpu_usec", "mem_atual_bytes", "mem_pico_bytes", "pgfault", "pgmajfault", "pgfault_minor",
    "io_rbytes", "io_wbytes", "io_rios", "io_wios", "oom_kill",
    "mem_efetiva_bytes", "swap_efetivo_bytes", "nano_cpus", "rede_efetiva",
    # ambiente
    "host_temp_c", "host_freq_khz", "host_mem_disponivel_kb", "host_swap_usado_kb", "host_na_tomada", "host_governador",
    # validação
    "validacao", "motivo", "detalhe",
]


def carregar_json(p):
    return json.loads(Path(p).read_text())


def carregar_configs(arquivos, filtro):
    cfgs = []
    for a in arquivos:
        d = carregar_json(RAIZ / a if not Path(a).is_absolute() else a)
        for c in d["configs"]:
            c.setdefault("exp", d.get("experimento"))
            c.setdefault("cache", "aquecido")
            c.setdefault("pacote", "padrao")
            c.setdefault("rede", "bridge")
            cfgs.append(c)
    if filtro:
        rx = re.compile(filtro)
        cfgs = [c for c in cfgs if rx.search(c["id"])]
    ids = [c["id"] for c in cfgs]
    assert len(ids) == len(set(ids)), "IDs de configuração duplicados"
    return cfgs


def montar_agenda(cfgs, n_frio, bloco, rng):
    """Repetições em blocos intercalados e sorteados (seed registrada)."""
    blocos = []
    for c in cfgs:
        for i in range(0, n_frio, bloco):
            blocos.append((c, list(range(i, min(i + bloco, n_frio)))))
    rng.shuffle(blocos)
    agenda = [(c, rep) for c, reps in blocos for rep in reps]
    ultimo = {}                       # a invocação quente roda após o ÚLTIMO frio de cada config
    for pos, (c, rep) in enumerate(agenda):
        ultimo[c["id"]] = pos
    return agenda, ultimo


def snapshot_ambiente(amb):
    def sh(cmd):
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return r.stdout.strip() or None
    snap = {
        "data": datetime.now().isoformat(timespec="seconds"),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "docker_version": sh("docker version --format '{{.Server.Version}}'"),
        "docker_storage_driver": sh("docker info --format '{{.Driver}}'"),
        "docker_cgroup_version": sh("docker info --format '{{.CgroupVersion}}'"),
        "docker_cgroup_driver": sh("docker info --format '{{.CgroupDriver}}'"),
        "fs_docker": sh("findmnt -no FSTYPE,SOURCE /var/lib/docker"),
        "swap": sh("swapon --show --noheadings"),
        "strace": sh("strace -V | head -1"),
        "perf": sh("perf --version"),
        "sebs_commit": sh(f"git -C {Path(amb.get('sebs_dir', '.')).expanduser()} rev-parse HEAD"),
        "imagens": {rt: sh(f"docker image inspect -f '{{{{.Id}}}}' {img}") for rt, img in amb.get("imagens", {}).items()},
        "host": coletores.condicoes_host(),
    }
    return snap


def verificar_ambiente(crit, host):
    """Retorna lista de violações dos critérios (provisórios até o piloto)."""
    v = []
    if crit.get("exigir_tomada") and host["na_tomada"] is False:
        v.append("notebook fora da tomada")
    t = host["temp_c"]
    if t is not None and crit.get("temp_max_c") and t > crit["temp_max_c"]:
        v.append(f"temperatura {t:.0f}C > {crit['temp_max_c']}C")
    s = host["swap_usado_kb"]
    if s is not None and crit.get("swap_max_kb") is not None and s > crit["swap_max_kb"]:
        v.append(f"swap em uso: {s} kB")
    m = host["mem_disponivel_kb"]
    if m is not None and crit.get("mem_min_disponivel_kb") and m < crit["mem_min_disponivel_kb"]:
        v.append(f"RAM disponível {m} kB")
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--configs", nargs="+", default=None, help="JSONs de configuração (padrão: e1..e4)")
    ap.add_argument("--filtro", default=None, help="regex sobre o id da configuração")
    ap.add_argument("--piloto", action="store_true", help="5 frios, 10 quentes por configuração")
    ap.add_argument("--n-frio", type=int, default=30)
    ap.add_argument("--n-quente", type=int, default=50)
    ap.add_argument("--bloco", type=int, default=5, help="tamanho do bloco de repetições intercaladas")
    ap.add_argument("--rodada", type=int, required=False, default=1)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--backend", choices=list(BACKENDS), default="docker")
    ap.add_argument("--tag", default="", help="rótulo no nome do arquivo (ex.: piloto, smoke)")
    ap.add_argument("--pausa-s", type=float, default=1.0, help="intervalo entre amostras (fora das medições)")
    ap.add_argument("--eventos", action="store_true", help="coletar docker events (relógio do daemon)")
    ap.add_argument("--drop-nivel", type=int, default=3, choices=[1, 2, 3])
    ap.add_argument("--ambiente", default="configs/ambiente_local.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.piloto:
        a.n_frio, a.n_quente, a.bloco, a.tag = 5, 10, 1, a.tag or "piloto"   # bloco=1: intercala totalmente, para enxergar deriva
    seed = a.seed if a.seed is not None else int(time.time())
    rng = random.Random(seed)

    amb = carregar_json(RAIZ / a.ambiente if not Path(a.ambiente).is_absolute() else a.ambiente)
    crit = carregar_json(RAIZ / "configs/criterios.json")
    wls = carregar_json(RAIZ / "configs/workloads.json")
    arquivos = a.configs or ["configs/e1_runtime_memoria.json", "configs/e2_pacote.json",
                             "configs/e3_rede.json", "configs/e4_cache.json"]
    cfgs = carregar_configs(arquivos, a.filtro)
    agenda, ultimo = montar_agenda(cfgs, a.n_frio, a.bloco, rng)

    print(f"{len(cfgs)} configurações | {a.n_frio} frios cada | {len(agenda)} amostras frias | "
          f"{a.n_quente} quentes após o último frio | seed={seed} | backend={a.backend}")
    if a.dry_run:
        for i, (c, rep) in enumerate(agenda[:40]):
            print(f"  {i:4d}  {c['id']:<22} rep={rep}{'  [+quentes]' if ultimo[c['id']] == i else ''}")
        if len(agenda) > 40:
            print(f"  ... ({len(agenda) - 40} restantes)")
        return

    opts = {"timeout_pronto_s": amb.get("timeout_pronto_s", 60), "timeout_req_s": amb.get("timeout_req_s", 60),
            "intervalo_sondagem_ms": amb.get("intervalo_sondagem_ms", 5), "eventos": a.eventos,
            "drop_nivel": a.drop_nivel}
    backend = BACKENDS[a.backend](amb, RAIZ)

    # validadores e eventos por workload
    wl_ctx = {}
    for chave in {c["workload"] for c in cfgs}:
        w = wls[chave]
        evento = w["evento"] if "evento" in w else carregar_json(RAIZ / w["evento_arquivo"])
        wl_ctx[chave] = {"evento": evento, "validador": medir.carregar_validador(RAIZ, w["benchmark"]),
                         "env": amb.get("env_por_workload", {}).get(chave, {})}
        if wl_ctx[chave]["validador"] is None:
            print(f"  aviso: validador do SeBS indisponível para {chave}; só o HTTP/formato serão conferidos")

    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    sufixo = f"_{a.tag}" if a.tag else ""
    destino = RAIZ / "resultados/brutos" / f"rodada{a.rodada}_{ts}{sufixo}.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    dir_ev = RAIZ / "resultados/rastros" / f"rodada{a.rodada}_{ts}{sufixo}_eventos"
    meta = {"args": vars(a), "seed": seed, "criterios": crit, "ambiente": snapshot_ambiente(amb),
            "configs": [c["id"] for c in cfgs], "agenda": [[c["id"], r] for c, r in agenda],
            "validadores_ausentes": [k for k, v in wl_ctx.items() if v["validador"] is None]}
    destino.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1, default=str))

    n_ok = n_falha = 0
    t_ini = time.time()
    with open(destino, "x", newline="") as f:           # 'x': nunca sobrescreve
        w = csv.DictWriter(f, fieldnames=COLUNAS, extrasaction="ignore")
        w.writeheader()
        try:
            for ordem, (c, rep) in enumerate(agenda):
                # critérios ambientais (provisórios até o piloto)
                for tentativa in range(int(crit.get("espera_max_s", 300) // 15) + 1):
                    viol = verificar_ambiente(crit, coletores.condicoes_host())
                    if not viol:
                        break
                    print(f"  ambiente fora do critério: {viol}; aguardando 15 s")
                    if "notebook fora da tomada" in viol:
                        raise SystemExit("Interrompido: notebook fora da tomada (dados já salvos).")
                    time.sleep(15)
                else:
                    raise SystemExit(f"Interrompido: ambiente fora do critério: {viol}")

                ctx = wl_ctx[c["workload"]]
                id_base = f"r{a.rodada}-{c['id']}-{rep:03d}"
                n_q = a.n_quente if ultimo[c["id"]] == ordem else 0
                linhas = medir.medir(backend, c, ctx["evento"], ctx["validador"], ctx["env"], amb, opts,
                                     n_q, id_base, dir_ev)
                for ln in linhas:
                    ln.update(exp=c["exp"], config_id=c["id"], rodada=a.rodada, repeticao=rep, ordem=ordem,
                              seed=seed, tag=a.tag, workload=c["workload"], runtime=c["runtime"], pacote=c["pacote"],
                              mem_mib=c["mem_mib"], mem_bytes=int(c["mem_mib"]) * 1024 * 1024, rede=c["rede"],
                              cache=c["cache"], backend=a.backend)
                    w.writerow({k: ("" if v is None else v) for k, v in ln.items()})
                f.flush()
                fria = linhas[0]
                if fria["validacao"] == "ok":
                    n_ok += 1
                else:
                    n_falha += 1
                print(f"[{ordem + 1:4d}/{len(agenda)}] {c['id']:<22} rep={rep:02d} "
                      f"{fria['validacao']:<11} cold_total={fria.get('t_cold_total_ms') or float('nan'):8.1f} ms"
                      f"{'  +' + str(len(linhas) - 1) + ' quentes' if len(linhas) > 1 else ''}")
                time.sleep(a.pausa_s)
        except KeyboardInterrupt:
            print("\nInterrompido pelo usuário; o CSV parcial foi preservado.")
    dur = time.time() - t_ini
    print(f"\nConcluído em {dur / 60:.1f} min: {n_ok} frias válidas, {n_falha} com falha/invalidação.\nCSV: {destino}")


if __name__ == "__main__":
    main()
