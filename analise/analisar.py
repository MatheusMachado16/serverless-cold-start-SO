#!/usr/bin/env python3
"""Análise dos CSVs brutos: estatísticas descritivas, diagnóstico metodológico e gráficos.

  ./analise/analisar.py                                  # todos os CSVs de resultados/brutos
  ./analise/analisar.py resultados/brutos/rodada0_*.csv  # arquivos específicos
  ./analise/analisar.py --saida piloto                   # prefixo dos arquivos gerados

Gera em analise/saida/: resumo_<p>.csv, comparacoes_<p>.csv, diagnostico_<p>.md e figuras fig_<p>_*.png
"""
from __future__ import annotations

import argparse
import glob
import itertools
import textwrap
from collections import namedtuple
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "analise" / "saida"
RNG = np.random.default_rng(12345)

# Fatores que definem uma configuração; comparações só entre configs que diferem em UM deles.
FATORES = ["runtime", "mem_mib", "pacote", "rede", "cache"]


def ic_bootstrap(x, fn=np.median, n=10_000, alfa=0.05):
    x = np.asarray(x, float)
    if len(x) < 3:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    est = fn(x[idx], axis=1)
    return tuple(np.quantile(est, [alfa / 2, 1 - alfa / 2]))


def holm(pvals):
    p = np.asarray(pvals, float)
    ordem = np.argsort(p)
    m = len(p)
    aj = np.empty(m)
    corrente = 0.0
    for rank, i in enumerate(ordem):
        corrente = max(corrente, (m - rank) * p[i])
        aj[i] = min(1.0, corrente)
    return aj


def desc(x):
    x = np.asarray(x, float)
    q1, q3 = np.quantile(x, [0.25, 0.75])
    return dict(n=len(x), media=x.mean(), mediana=np.median(x), minimo=x.min(), maximo=x.max(),
                dp=x.std(ddof=1) if len(x) > 1 else np.nan, iqr=q3 - q1,
                p95=np.quantile(x, 0.95), p99=np.quantile(x, 0.99))


def carregar(arquivos):
    dfs = []
    for a in arquivos:
        d = pd.read_csv(a)
        d["arquivo"] = Path(a).name
        dfs.append(d)
    return pd.concat(dfs, ignore_index=True)


def resumo(frio_ok, quente_ok):
    linhas = []
    for cfg, g in frio_ok.groupby("config_id", sort=False):
        d = desc(g["t_cold_total_ms"])
        lo, hi = ic_bootstrap(g["t_cold_total_ms"])
        q = quente_ok[quente_ok.config_id == cfg]["lat_req_ms"]
        mediana_q = q.median() if len(q) else np.nan
        linhas.append({"config_id": cfg, "exp": g["exp"].iloc[0], "workload": g["workload"].iloc[0],
                       "runtime": g["runtime"].iloc[0], "mem_mib": g["mem_mib"].iloc[0], "rede": g["rede"].iloc[0],
                       "cache": g["cache"].iloc[0], "pacote": g["pacote"].iloc[0], **d,
                       "cv": d["dp"] / d["media"], "ic95_med_lo": lo, "ic95_med_hi": hi,
                       "ready_mediana": g["t_ready_ms"].median(), "req_cold_mediana": g["t_req_cold_ms"].median(),
                       "quente_n": len(q), "quente_mediana": mediana_q,
                       "overhead_mediana": d["mediana"] - mediana_q if len(q) else np.nan,
                       "p99_exploratorio": d["n"] < 100})
    return pd.DataFrame(linhas)


def _kruskal(*g):
    """Kruskal-Wallis; cálculo manual se o scipy desta máquina (Python 3.14) falhar com AttributeError."""
    try:
        return stats.kruskal(*g)
    except AttributeError:
        todos = np.concatenate([np.asarray(x, float) for x in g])
        r = stats.rankdata(todos)
        n, i, h = len(todos), 0, 0.0
        for x in g:
            k = len(x)
            h += r[i:i + k].sum() ** 2 / k
            i += k
        h = 12.0 / (n * (n + 1)) * h - 3 * (n + 1)
        t = stats.tiecorrect(r)
        h = h / t if t else float("nan")
        R = namedtuple("KruskalResult", "statistic pvalue")
        return R(h, float(stats.chi2.sf(h, len(g) - 1)))


def _num(x):
    """Converte para array float e descarta vazios (evita dtype object nos testes do scipy)."""
    a = np.asarray(list(x), dtype=float)
    return a[~np.isnan(a)]


def _spearman(x, y):
    """Spearman com entradas convertidas para float, ignorando pares vazios."""
    x = np.asarray(list(x), dtype=float)
    y = np.asarray(list(y), dtype=float)
    m = ~(np.isnan(x) | np.isnan(y))
    return stats.spearmanr(x[m], y[m])


def _pares_validos(cfg, exp):
    """Pares de configurações do mesmo workload que diferem em exatamente UM fator
    (README, seção 10). No teste A/A (SMOKE) as configurações são idênticas: 0 fatores."""
    out = []
    for a, b in itertools.combinations(cfg.index, 2):
        if cfg.loc[a, "workload"] != cfg.loc[b, "workload"]:
            continue
        dif = [f for f in FATORES if cfg.loc[a, f] != cfg.loc[b, f]]
        if len(dif) == 1:
            out.append((a, b, dif[0]))
        elif len(dif) == 0 and exp == "SMOKE":
            out.append((a, b, "-"))
    return out


def comparacoes(frio_ok):
    """Kruskal-Wallis por família de configurações e Mann-Whitney (grupos independentes) apenas entre
    configurações que diferem em um único fator, com correção de Holm dentro de cada experimento."""
    out = []
    cfg = frio_ok.drop_duplicates("config_id").set_index("config_id")[["workload"] + FATORES]
    for exp, g in frio_ok.groupby("exp"):
        grupos = {c: v["t_cold_total_ms"].values for c, v in g.groupby("config_id")}
        if len(grupos) < 2:
            continue
        res = []
        for a, b, fator in _pares_validos(cfg.loc[list(grupos)], exp):
            u, p = stats.mannwhitneyu(_num(grupos[a]), _num(grupos[b]), alternative="two-sided")
            rbc = 1 - 2 * u / (len(grupos[a]) * len(grupos[b]))          # correlação bisserial por postos
            # Kruskal-Wallis na família que varia só neste fator (mesmo workload e demais fatores iguais a `a`),
            # para que a diferença entre runtimes não contamine o teste de memória, pacote, rede ou cache.
            fam = [c for c in grupos if fator != "-" and cfg.loc[c, "workload"] == cfg.loc[a, "workload"]
                   and all(cfg.loc[c, f] == cfg.loc[a, f] for f in FATORES if f != fator)]
            kw = _kruskal(*[grupos[c] for c in fam]) if len(fam) > 2 else None
            res.append((a, b, fator, p, rbc, np.median(grupos[a]) - np.median(grupos[b]),
                        kw.pvalue if kw else np.nan))
        if not res:
            continue
        aj = holm([r[3] for r in res])
        for (a, b, fator, p, rbc, dm, kp), pa in zip(res, aj):
            out.append(dict(exp=exp, fator=fator, a=a, b=b, dif_mediana_ms=dm, efeito_rbc=rbc, p=p, p_holm=pa,
                            kruskal_p=kp))
    return pd.DataFrame(out)


def diagnostico(df, frio, frio_ok, quente, res, comp):
    """Procura problemas metodológicos. Retorna lista de (severidade, achado)."""
    ach = []
    # 1. backend
    bks = df["backend"].unique().tolist()
    if "processo" in bks:
        ach.append(("ATENÇÃO", "Há dados do backend `processo` (sem Docker). Servem para validar o pipeline; "
                    "NÃO são cold start de contêiner e não devem entrar em resultados do estudo."))
    # 2. falhas
    falhas = frio[frio.validacao != "ok"]
    if len(falhas):
        por = falhas.groupby(["config_id", "validacao", "motivo"]).size().reset_index(name="n")
        ach.append(("ATENÇÃO", f"{len(falhas)} de {len(frio)} amostras frias não válidas "
                    f"({100 * len(falhas) / len(frio):.1f}%): " + "; ".join(
                        f"{r.config_id}: {r.validacao}/{r.motivo} x{r.n}" for r in por.itertuples())))
    else:
        ach.append(("OK", f"Todas as {len(frio)} amostras frias foram válidas (resposta 200 e saída validada)."))
    # 3. deriva temporal (ordem de execução x latência)
    for cfg, g in frio_ok.groupby("config_id"):
        if len(g) >= 10:
            rho, p = _spearman(g["ordem"], g["t_cold_total_ms"])
            if p < 0.05:
                ach.append(("ATENÇÃO", f"{cfg}: latência correlacionada com a ordem de execução "
                            f"(Spearman rho={rho:+.2f}, p={p:.3f}) — possível deriva térmica/de cache (vários testes: p não corrigido)."))
    # 4. primeira amostra vs demais
    for cfg, g in frio_ok.sort_values("ordem").groupby("config_id"):
        if len(g) >= 10:
            prim, resto = g["t_cold_total_ms"].iloc[0], g["t_cold_total_ms"].iloc[1:]
            if prim > resto.median() + 3 * stats.iqr(_num(resto)) / 1.349:
                ach.append(("INFO", f"{cfg}: a primeira amostra ({prim:.0f} ms) destoa da mediana ({resto.median():.0f} ms)."))
    # 5. variabilidade e tamanho de amostra
    pequeno = bool(len(res)) and res["n"].max() < 30
    for r in res.itertuples():
        if r.n >= 5 and r.cv > 0.15:
            ach.append(("ATENÇÃO", f"{r.config_id}: CV = {r.cv:.0%}; variabilidade alta"
                        + (" (com n pequeno, um único pico já provoca isso)." if r.n < 30 else ".")))
    if len(res):
        if pequeno:
            ach.append(("INFO", "Estimativa de amostras necessárias não calculada: com n < 30 por configuração "
                        "o desvio padrão é instável. Recalcular com a rodada 1 (30 por configuração)."))
        else:
            n_alvo = (1.96 * res["dp"] / (0.05 * res["media"])) ** 2
            ach.append(("INFO", f"Amostras frias necessárias para IC95% da média com ±5% de precisão: "
                        f"mediana entre configs = {np.ceil(n_alvo.median()):.0f}, máximo = {np.ceil(n_alvo.max()):.0f} "
                        f"(plano: 90 por configuração)."))
    # 6. composição do tempo: prontidão x primeira requisição
    r_ready = frio_ok["t_ready_ms"] / frio_ok["t_cold_total_ms"]
    ach.append(("INFO", f"Fração mediana do T_cold_total gasta até a prontidão: {r_ready.median():.0%} "
                f"(o restante é a primeira requisição)."))
    if "srv_import_ms" in frio_ok and frio_ok["srv_import_ms"].notna().any():
        ach.append(("INFO", f"Python: o SeBS importa a função DENTRO da 1ª requisição (srv_import_ms mediano = "
                    f"{frio_ok['srv_import_ms'].median():.2f} ms). Assim `T_ready` não inclui o import da aplicação em "
                    "Python, mas inclui em Node.js (que faz `require` ao subir). Só `T_cold_total` é comparável entre runtimes."))
    gap = frio_ok["gap_ready_req_ms"]
    ach.append(("INFO", f"Intervalo entre t_ready e t_req: mediana {gap.median():.2f} ms, máx {gap.max():.2f} ms "
                f"(sondagem a cada {frio_ok['intervalo_sondagem_ms'].iloc[0]:.0f} ms)."))
    # 7. quentes
    if len(quente) == 0:
        ach.append(("ATENÇÃO", "Não há invocações quentes: o overhead não pode ser calculado."))
    else:
        for cfg, g in quente.groupby("config_id"):
            if len(g) >= 20:
                lag1 = pd.Series(g["lat_req_ms"].values).autocorr(1)
                if abs(lag1) > 0.3:
                    ach.append(("INFO", f"{cfg}: autocorrelação lag-1 das quentes = {lag1:+.2f}; IC deve respeitar a dependência."))
    # 8. A/A
    aa = comp[comp.exp == "SMOKE"] if len(comp) else comp
    for r in aa.itertuples():
        ach.append(("INFO", f"Teste A/A ({r.a} x {r.b}, configs idênticas): diferença de medianas = {r.dif_mediana_ms:+.1f} ms, "
                    f"p = {r.p:.3f}. {'Diferença não detectada com este n (isso não prova ausência de viés; serve de piso de ruído).' if r.p >= 0.05 else 'DIFERENÇA ENTRE CONFIGS IDÊNTICAS: investigar fonte de viés (ordem, deriva, interferência).'}"))
    # 9. métricas ausentes
    ausentes = [c for c in ["cpu_usec", "mem_pico_bytes", "pgfault_minor", "pgmajfault", "io_rbytes", "host_temp_c", "host_freq_khz"]
                if c in frio_ok and frio_ok[c].isna().all()]
    if ausentes:
        ach.append(("ATENÇÃO", "Métricas sem nenhuma observação (registradas como ausentes): " + ", ".join(ausentes)))
    # 10. contexto de ambiente
    if frio_ok["host_na_tomada"].isna().all() or frio_ok["host_temp_c"].isna().all():
        ach.append(("ATENÇÃO", "Sem leitura de temperatura/tomada: os critérios ambientais não puderam ser verificados nesta máquina."))
    return ach


# ---------------------------------------------------------------- gráficos
# Cores: slots 1 a 4 da paleta categórica de referência (azul, laranja, verde-água, amarelo).
SUP, TXT, TXT2, GRADE = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
AZUL, LARANJA, AQUA, AMARELO = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
NOME_RT = {"python": "Python", "nodejs": "Node.js"}
NOME_WL = {"A1": "A1 · crud-api", "A2": "A2 · thumbnailer"}
ORDEM_RT = ["python", "nodejs"]


def marca_dagua(ax, df):
    if "processo" in df["backend"].unique():
        ax.text(0.5, 0.5, "VALIDAÇÃO DO PIPELINE\nbackend processo (sem Docker)\nnão é resultado do estudo",
                transform=ax.transAxes, ha="center", va="center", fontsize=13, color="gray", alpha=0.35,
                rotation=18, zorder=0)


def _estilo(ax, eixo="y"):
    ax.set_facecolor(SUP)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)
    ax.tick_params(colors=TXT2, labelsize=10, length=0)
    ax.set_axisbelow(True)
    ax.grid(axis=eixo, color=GRADE, lw=0.8)


def _moldura(fig, titulo, sub, topo=1.25, base=0.95):
    """Título e subtítulo alinhados à esquerda; margens definidas em polegadas."""
    h = fig.get_figheight()
    fig.patch.set_facecolor(SUP)
    sub = textwrap.fill(sub, width=max(40, int(fig.get_figwidth() * 11)))
    extra = 0.2 * (sub.count("\n"))
    fig.text(0.015, 1 - 0.18 / h, titulo, ha="left", va="top", fontsize=13.5, fontweight="bold", color=TXT)
    fig.text(0.015, 1 - 0.62 / h, sub, ha="left", va="top", fontsize=10, color=TXT2, linespacing=1.4)
    fig.subplots_adjust(top=1 - (topo + extra) / h, bottom=base / h)


def _legenda(fig, rotulos, cores):
    hs = [plt.Line2D([], [], marker="o", ls="", color=c, markersize=8, label=r) for c, r in zip(cores, rotulos)]
    fig.legend(handles=hs, loc="lower center", ncol=len(hs), frameon=False, fontsize=10, labelcolor=TXT,
               bbox_to_anchor=(0.5, 0.0))


def graf_comparacao(frio_ok, df, exp, coluna, niveis, rotulos, titulo_fn, caminho):
    """Dois ou três níveis de um fator (azul, laranja, verde-água), por runtime e por aplicação.
    Cada ponto é uma amostra fria; o traço é a mediana. Retorna False se não houver dados."""
    d = frio_ok[frio_ok.exp == exp]
    if d.empty:
        return False
    cores = (AZUL, LARANJA, AQUA)[:len(niveis)]
    passo = 0.5 if len(niveis) == 2 else 0.34
    paineis = sorted(d.workload.unique())
    fig, axes = plt.subplots(1, len(paineis), figsize=(max(4.3 * len(paineis) + 1.2, 7.4), 5.6), sharey=True, squeeze=False)
    rng = np.random.default_rng(7)
    ymax = float(d.t_cold_total_ms.max())
    difs = []
    for ax, wl in zip(axes[0], paineis):
        _estilo(ax)
        marca_dagua(ax, df)
        dd = d[d.workload == wl]
        for i, rt in enumerate(ORDEM_RT):
            meds = []
            for j, (nv, cor) in enumerate(zip(niveis, cores)):
                v = dd[(dd.runtime == rt) & (dd[coluna] == nv)].t_cold_total_ms.values
                if len(v) == 0:
                    continue
                x = i + (j - (len(niveis) - 1) / 2) * passo
                ax.scatter(x + rng.uniform(-0.05, 0.05, len(v)), v, s=46, color=cor, edgecolor=SUP,
                           linewidth=1.2, zorder=3, alpha=0.9)
                m = float(np.median(v))
                meds.append(m)
                ax.hlines(m, x - 0.11, x + 0.11, color=cor, lw=3, zorder=4)
                ax.text(x + 0.13, m, f"{m:.0f}", va="center", ha="left", fontsize=9, color=TXT)
            if len(meds) == len(niveis):
                dif = meds[-1] - meds[0]
                pct = 100 * dif / meds[0]
                difs.append((dif, pct))
                ax.text(i, ymax * 1.17, f"{dif:+.0f} ms ({pct:+.0f}%)", ha="center", va="center",
                        fontsize=10, fontweight="bold", color=TXT)
        ax.set_xticks(range(len(ORDEM_RT)))
        ax.set_xticklabels([NOME_RT[r] for r in ORDEM_RT], fontsize=11, color=TXT)
        ax.set_xlim(-0.55, len(ORDEM_RT) - 0.4)
        ax.set_title(NOME_WL.get(wl, wl), loc="left", fontsize=11, color=TXT, pad=10)
    axes[0][0].set_ylim(0, ymax * 1.27)
    axes[0][0].set_ylabel("T_cold_total (ms)", color=TXT2, fontsize=10)
    if not difs:
        plt.close(fig)
        return False
    lo, hi = min(x[0] for x in difs), max(x[0] for x in difs)
    plo, phi = min(x[1] for x in difs), max(x[1] for x in difs)
    titulo, sub = titulo_fn(lo, hi, plo, phi)
    _moldura(fig, titulo, sub, topo=1.45, base=0.95)
    _legenda(fig, rotulos, cores)
    fig.savefig(caminho, dpi=160, facecolor=SUP)
    plt.close(fig)
    return True


def graf_pacote(frio_ok, df, caminho):
    return graf_comparacao(
        frio_ok, df, "E2", "pacote", ("minimo", "padrao", "ampliado"),
        ("pacote mínimo", "pacote padrão", "pacote ampliado"),
        lambda lo, hi, plo, phi: (
            f"Do pacote mínimo ao ampliado, o cold start varia de {lo:+.0f} a {hi:+.0f} ms",
            f"Variação de {plo:+.0f}% a {phi:+.0f}% (ampliado em relação ao mínimo). "
            "Cada ponto é uma amostra fria; o traço é a mediana."),
        caminho)


def graf_cache(frio_ok, df, caminho):
    return graf_comparacao(
        frio_ok, df, "E4", "cache", ("aquecido", "descartado"), ("cache aquecido", "cache descartado"),
        lambda lo, hi, plo, phi: (
            f"Descartar os caches do host altera o cold start em {lo:+.0f} a {hi:+.0f} ms",
            f"Variação de {plo:+.0f}% a {phi:+.0f}% sobre o cache aquecido (drop_caches=3: page cache e metadados). "
            "Cada ponto é uma amostra fria; o traço é a mediana."),
        caminho)


def graf_rede(frio_ok, df, caminho):
    return graf_comparacao(
        frio_ok, df, "E3", "rede", ("host", "bridge"), ("rede host", "rede bridge"),
        lambda lo, hi, plo, phi: (
            f"A rede bridge altera o cold start em {lo:+.0f} a {hi:+.0f} ms em relação à rede host",
            f"Variação de {plo:+.0f}% a {phi:+.0f}%. Cada ponto é uma amostra fria; o traço é a mediana."),
        caminho)


def graf_memoria(frio_ok, df, caminho):
    d = frio_ok[frio_ok.exp == "E1"]
    if d.empty:
        return False
    mems = sorted(d.mem_mib.unique())
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    _estilo(ax)
    marca_dagua(ax, df)
    rng = np.random.default_rng(7)
    maxdif = 0.0
    rotulos_fim = []
    for rt, cor, desl in zip(ORDEM_RT, (AZUL, LARANJA), (-0.08, 0.08)):
        meds = []
        for k, mem in enumerate(mems):
            v = d[(d.runtime == rt) & (d.mem_mib == mem)].t_cold_total_ms.values
            ax.scatter(k + desl + rng.uniform(-0.04, 0.04, len(v)), v, s=40, color=cor, edgecolor=SUP,
                       linewidth=1.2, alpha=0.85, zorder=3)
            meds.append(float(np.median(v)))
        ax.plot(range(len(mems)), meds, color=cor, lw=2, zorder=2)
        maxdif = max(maxdif, max(meds) - min(meds))
        rotulos_fim.append((meds[-1], f"{NOME_RT[rt]}  {meds[-1]:.0f} ms"))
    # rótulos diretos no fim das linhas, afastados para não se sobrepor
    ymax_e1 = float(d.t_cold_total_ms.max()) * 1.2
    ys = [y for y, _ in rotulos_fim]
    if abs(ys[0] - ys[1]) < 0.07 * ymax_e1:
        meio, folga = (ys[0] + ys[1]) / 2, 0.035 * ymax_e1
        pos = [meio + folga, meio - folga] if ys[0] >= ys[1] else [meio - folga, meio + folga]
    else:
        pos = ys
    for (y, txt), yp in zip(rotulos_fim, pos):
        ax.text(len(mems) - 1 + 0.22, yp, txt, color=TXT, va="center", fontsize=10)
    ax.set_xticks(range(len(mems)))
    ax.set_xticklabels([f"{m} MiB" for m in mems], fontsize=11, color=TXT)
    ax.set_xlim(-0.4, len(mems) - 1 + 1.5)
    ax.set_ylim(0, float(d.t_cold_total_ms.max()) * 1.2)
    ax.set_ylabel("T_cold_total (ms)", color=TXT2, fontsize=10)
    ax.set_xlabel("limite de memória do contêiner", color=TXT2, fontsize=10)
    pico = d.mem_pico_bytes.max() / 1e6
    folga_txt = "abaixo" if pico * 1e6 < mems[0] * 1024 * 1024 else "ACIMA"
    _moldura(fig, f"Cold start por limite de memória ({mems[0]} a {mems[-1]} MiB)",
             f"As medianas variam até {maxdif:.0f} ms entre os níveis; o pico de memória medido foi de {pico:.0f} MB, "
             f"{folga_txt} do menor limite. Cada ponto é uma amostra fria.", topo=1.1, base=1.0)
    _legenda(fig, [NOME_RT[r] for r in ORDEM_RT], (AZUL, LARANJA))
    fig.savefig(caminho, dpi=160, facecolor=SUP)
    plt.close(fig)
    return True


def graf_fases(frio_ok, quente_ok, df, caminho):
    """Mediana de cada fase do cold start, uma barra por configuração, agrupadas por experimento."""
    f = frio_ok.copy()
    f["criacao"] = f["t_created_ms"]
    f["inicio"] = f["t_started_ms"] - f["t_created_ms"]
    f["pronto"] = f["t_ready_ms"] - f["t_started_ms"]
    f["requisicao"] = f["t_cold_total_ms"] - f["t_ready_ms"]
    fases = [("criacao", "criar contêiner (docker create)", AZUL), ("inicio", "iniciar (docker start)", LARANJA),
             ("pronto", "iniciar até ficar pronto", AQUA), ("requisicao", "1ª requisição", AMARELO)]
    cfg = f.drop_duplicates("config_id")[["config_id", "exp", "runtime", "workload", "mem_mib", "pacote", "rede", "cache"]].copy()
    cfg["_rt"] = cfg.runtime.map({"python": 0, "nodejs": 1})
    cfg["_pk"] = cfg.pacote.map({"minimo": 0, "padrao": 1, "ampliado": 2})
    cfg["_rd"] = cfg.rede.map({"host": 0, "bridge": 1})
    cfg["_ca"] = cfg.cache.map({"aquecido": 0, "descartado": 1})
    cfg = cfg.sort_values(["exp", "workload", "_rt", "mem_mib", "_pk", "_rd", "_ca"]).reset_index(drop=True)
    meds = f.groupby("config_id")[[c for c, _, _ in fases]].median().loc[cfg.config_id]
    ypos, y, ant = [], 0.0, None
    for _, r in cfg.iterrows():
        if ant is not None and r.exp != ant:
            y += 0.9
        ypos.append(y)
        ant = r.exp
        y += 1.0
    h = 0.27 * y + 2.7
    fig, ax = plt.subplots(figsize=(10, h))
    _estilo(ax, eixo="x")
    marca_dagua(ax, df)
    esq = np.zeros(len(cfg))
    for col, rot, cor in fases:
        v = meds[col].values
        ax.barh(ypos, v, left=esq, height=0.74, color=cor, edgecolor=SUP, linewidth=1.2)
        esq = esq + v
    for yy, tot in zip(ypos, esq):
        ax.text(tot + 12, yy, f"{tot:.0f}", va="center", ha="left", fontsize=8.5, color=TXT2)
    ax.set_yticks(ypos)
    ax.set_yticklabels(cfg.config_id, fontsize=9, color=TXT)
    ax.invert_yaxis()
    ax.set_xlim(0, esq.max() * 1.08)
    ax.set_xlabel("ms (mediana de cada fase; número ao fim da barra = soma das medianas)", color=TXT2, fontsize=10)
    ax.grid(axis="y", visible=False)
    cria, ini = f["criacao"].median(), f["inicio"].median()
    _moldura(fig, "Onde o tempo do cold start é gasto",
             f"Mediana geral: {cria:.0f} ms para criar e {ini:.0f} ms para iniciar o contêiner. Node carrega a "
             "função antes de ficar pronto; Python, na 1ª requisição.", topo=1.1, base=1.05)
    ax.set_position([0.13, 1.05 / h, 0.84, 1 - (1.35 + 1.05) / h])
    _legenda(fig, [r for _, r, _ in fases], [c for _, _, c in fases])
    fig.savefig(caminho, dpi=160, facecolor=SUP)
    plt.close(fig)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivos", nargs="*")
    ap.add_argument("--saida", default="analise")
    a = ap.parse_args()
    arqs = a.arquivos or sorted(glob.glob(str(RAIZ / "resultados/brutos/*.csv")))
    if not arqs:
        raise SystemExit("Nenhum CSV encontrado em resultados/brutos/.")
    SAIDA.mkdir(parents=True, exist_ok=True)
    df = carregar(arqs)
    frio = df[df.tipo == "frio"]
    frio_ok = frio[frio.validacao == "ok"]
    quente = df[df.tipo == "quente"]
    quente_ok = quente[quente.validacao == "ok"]

    res = resumo(frio_ok, quente_ok)
    comp = comparacoes(frio_ok)
    res.to_csv(SAIDA / f"resumo_{a.saida}.csv", index=False)
    if len(comp):
        comp.to_csv(SAIDA / f"comparacoes_{a.saida}.csv", index=False)
    ach = diagnostico(df, frio, frio_ok, quente, res, comp)

    # Todas as figuras são geradas a cada análise; experimentos ausentes do CSV são pulados com aviso.
    figuras = [("e1_memoria", lambda c: graf_memoria(frio_ok, df, c)),
               ("e2_pacote", lambda c: graf_pacote(frio_ok, df, c)),
               ("e3_rede", lambda c: graf_rede(frio_ok, df, c)),
               ("e4_cache", lambda c: graf_cache(frio_ok, df, c)),
               ("fases", lambda c: graf_fases(frio_ok, quente_ok, df, c))]
    for nome, fn in figuras:
        if fn(SAIDA / f"fig_{a.saida}_{nome}.png") is False:
            print(f"  sem dados para {nome}: figura pulada")

    md = [f"# Diagnóstico — {a.saida}", "", f"Arquivos: {', '.join(sorted(df['arquivo'].unique()))}", "",
          f"Amostras: {len(frio)} frias ({len(frio_ok)} válidas), {len(quente)} quentes.", "", "## Achados", ""]
    md += [f"- **{s}** — {t}" for s, t in ach]
    cols = ["config_id", "n", "mediana", "ic95_med_lo", "ic95_med_hi", "media", "dp", "cv", "iqr", "p95", "p99",
            "ready_mediana", "quente_mediana", "overhead_mediana"]
    md += ["", "## Resumo por configuração (ms)", "", res[cols].round(2).to_markdown(index=False)]
    if len(comp):
        md += ["", "## Comparações (Mann–Whitney entre configurações que diferem em um fator; Holm por experimento)",
               "", comp.round(4).to_markdown(index=False)]
    md += ["", "_p99 é exploratório com menos de 100 amostras por configuração._"]
    (SAIDA / f"diagnostico_{a.saida}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nArquivos em {SAIDA}")


if __name__ == "__main__":
    main()