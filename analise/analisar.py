#!/usr/bin/env python3
"""Análise dos CSVs brutos: estatísticas descritivas, diagnóstico metodológico e gráficos.

  ./analise/analisar.py                                  # todos os CSVs de resultados/brutos
  ./analise/analisar.py resultados/brutos/rodada0_*.csv  # arquivos específicos
  ./analise/analisar.py --saida piloto                   # prefixo dos arquivos gerados

Gera em analise/saida/: resumo_<p>.csv, diagnostico_<p>.md e figuras fig_<p>_*.png
"""
from __future__ import annotations

import argparse
import glob
import itertools
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


def comparacoes(frio_ok):
    """Kruskal-Wallis por experimento e Mann-Whitney par a par com Holm (grupos independentes)."""
    out = []
    for exp, g in frio_ok.groupby("exp"):
        grupos = {c: v["t_cold_total_ms"].values for c, v in g.groupby("config_id")}
        if len(grupos) < 2:
            continue
        kw = stats.kruskal(*grupos.values()) if len(grupos) > 2 else None
        pares = list(itertools.combinations(grupos, 2))
        res = []
        for a, b in pares:
            u, p = stats.mannwhitneyu(grupos[a], grupos[b], alternative="two-sided")
            rbc = 1 - 2 * u / (len(grupos[a]) * len(grupos[b]))          # correlação bisserial por postos
            res.append((a, b, p, rbc, np.median(grupos[a]) - np.median(grupos[b])))
        aj = holm([r[2] for r in res])
        for (a, b, p, rbc, dm), pa in zip(res, aj):
            out.append(dict(exp=exp, a=a, b=b, dif_mediana_ms=dm, efeito_rbc=rbc, p=p, p_holm=pa,
                            kruskal_p=kw.pvalue if kw else np.nan))
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
            rho, p = stats.spearmanr(g["ordem"], g["t_cold_total_ms"])
            if p < 0.05:
                ach.append(("ATENÇÃO", f"{cfg}: latência correlacionada com a ordem de execução "
                            f"(Spearman rho={rho:+.2f}, p={p:.3f}) — possível deriva térmica/de cache (vários testes: p não corrigido)."))
    # 4. primeira amostra vs demais
    for cfg, g in frio_ok.sort_values("ordem").groupby("config_id"):
        if len(g) >= 10:
            prim, resto = g["t_cold_total_ms"].iloc[0], g["t_cold_total_ms"].iloc[1:]
            if prim > resto.median() + 3 * stats.iqr(resto) / 1.349:
                ach.append(("INFO", f"{cfg}: a primeira amostra ({prim:.0f} ms) destoa da mediana ({resto.median():.0f} ms)."))
    # 5. variabilidade e tamanho de amostra
    for r in res.itertuples():
        if r.n >= 5 and r.cv > 0.15:
            ach.append(("ATENÇÃO", f"{r.config_id}: CV = {r.cv:.0%}; variabilidade alta."))
    if len(res):
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
def marca_dagua(ax, df):
    if "processo" in df["backend"].unique():
        ax.text(0.5, 0.5, "VALIDAÇÃO DO PIPELINE\nbackend processo (sem Docker)\nnão é resultado do estudo",
                transform=ax.transAxes, ha="center", va="center", fontsize=13, color="gray", alpha=0.35,
                rotation=18, zorder=0)


def graf_boxplot(frio_ok, df, caminho):
    cfgs = list(frio_ok["config_id"].unique())
    dados = [frio_ok[frio_ok.config_id == c]["t_cold_total_ms"].values for c in cfgs]
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(cfgs) + 3), 4.8))
    marca_dagua(ax, df)
    ax.boxplot(dados, tick_labels=cfgs, showfliers=False, widths=0.5)
    for i, d in enumerate(dados, 1):
        ax.scatter(RNG.normal(i, 0.05, len(d)), d, s=10, alpha=0.5, zorder=3)
    ax.set_ylabel("T_cold_total (ms)")
    ax.set_title("Latência de cold start por configuração")
    ax.grid(axis="y", alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


def graf_ecdf(frio_ok, df, caminho):
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    marca_dagua(ax, df)
    for c, g in frio_ok.groupby("config_id", sort=False):
        x = np.sort(g["t_cold_total_ms"].values)
        ax.step(x, np.arange(1, len(x) + 1) / len(x), where="post", label=c)
    ax.set_xlabel("T_cold_total (ms)")
    ax.set_ylabel("Fração acumulada")
    ax.set_title("Distribuição acumulada (CDF empírica)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


def graf_fases(frio_ok, quente_ok, df, caminho):
    """Medianas por fase: criação, início, prontidão e 1ª requisição (+ referência quente)."""
    cfgs = list(frio_ok["config_id"].unique())
    f = frio_ok.copy()
    f["criacao"] = f["t_created_ms"]
    f["inicio"] = f["t_started_ms"] - f["t_created_ms"]
    f["pronto"] = f["t_ready_ms"] - f["t_started_ms"]
    f["requisicao"] = f["t_cold_total_ms"] - f["t_ready_ms"]
    fases = [("criacao", "criação (docker create)"), ("inicio", "início (docker start)"),
             ("pronto", "início até prontidão"), ("requisicao", "1ª requisição (+ gap)")]
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(cfgs) + 3), 4.8))
    marca_dagua(ax, df)
    base = np.zeros(len(cfgs))
    for col, rot in fases:
        v = np.array([f[f.config_id == c][col].median() for c in cfgs])
        ax.bar(cfgs, v, bottom=base, label=rot)
        base += v
    q = [quente_ok[quente_ok.config_id == c]["lat_req_ms"].median() for c in cfgs]
    ax.scatter(cfgs, q, marker="D", color="k", zorder=5, label="requisição quente (mediana)")
    ax.set_ylabel("ms (mediana de cada fase)")
    ax.set_title("Composição do cold start")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.grid(axis="y", alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


def graf_ordem(frio_ok, df, caminho):
    """Latência pela ordem de execução: ajuda a ver deriva e efeito de blocos."""
    fig, ax = plt.subplots(figsize=(7, 4))
    marca_dagua(ax, df)
    for c, g in frio_ok.groupby("config_id", sort=False):
        g = g.sort_values("ordem")
        ax.plot(g["ordem"], g["t_cold_total_ms"], "o-", ms=3, lw=0.6, alpha=0.8, label=c)
    ax.set_xlabel("ordem de execução na rodada")
    ax.set_ylabel("T_cold_total (ms)")
    ax.set_title("Latência × ordem de execução (deriva)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


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

    graf_boxplot(frio_ok, df, SAIDA / f"fig_{a.saida}_boxplot.png")
    graf_ecdf(frio_ok, df, SAIDA / f"fig_{a.saida}_ecdf.png")
    graf_fases(frio_ok, quente_ok, df, SAIDA / f"fig_{a.saida}_fases.png")
    graf_ordem(frio_ok, df, SAIDA / f"fig_{a.saida}_ordem.png")

    md = [f"# Diagnóstico — {a.saida}", "", f"Arquivos: {', '.join(sorted(df['arquivo'].unique()))}", "",
          f"Amostras: {len(frio)} frias ({len(frio_ok)} válidas), {len(quente)} quentes.", "", "## Achados", ""]
    md += [f"- **{s}** — {t}" for s, t in ach]
    cols = ["config_id", "n", "mediana", "ic95_med_lo", "ic95_med_hi", "media", "dp", "cv", "iqr", "p95", "p99",
            "ready_mediana", "quente_mediana", "overhead_mediana"]
    md += ["", "## Resumo por configuração (ms)", "", res[cols].round(2).to_markdown(index=False)]
    if len(comp):
        md += ["", "## Comparações (Mann–Whitney, correção de Holm)", "", comp.round(4).to_markdown(index=False)]
    md += ["", "_p99 é exploratório com menos de 100 amostras por configuração._"]
    (SAIDA / f"diagnostico_{a.saida}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nArquivos em {SAIDA}")


if __name__ == "__main__":
    main()
