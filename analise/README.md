# analise

Estatística e gráficos a partir dos CSVs de `resultados/brutos/`.

## Como rodar

```bash
./analise/analisar.py                                   # todos os CSVs de resultados/brutos
./analise/analisar.py resultados/brutos/rodada1_*.csv   # arquivos específicos
./analise/analisar.py --saida rodada1                   # prefixo dos arquivos gerados (padrão: "analise")
```

A análise lê **todos** os CSVs da pasta. Testes e ensaios não devem ficar em `resultados/brutos/`; para analisar um arquivo isolado, passe o caminho dele.

## O que é gerado em `saida/`

| Arquivo | Conteúdo |
| --- | --- |
| `resumo_<p>.csv` | Por configuração: n, média, mediana, desvio padrão, IQR, p95, p99, CV, IC95% da mediana (bootstrap), mediana da invocação quente e overhead |
| `comparacoes_<p>.csv` | Mann-Whitney com correção de Holm (por experimento) entre configurações que diferem em um único fator (runtime, memória, pacote, rede ou cache) e usam o mesmo workload; a coluna `fator` indica qual. A coluna `kruskal_p` traz o Kruskal-Wallis da família de configurações que varia só nesse fator, para que a diferença entre runtimes não contamine os demais testes |
| `diagnostico_<p>.md` | Achados metodológicos (falhas, variabilidade, deriva, prontidão, métricas ausentes) e as tabelas acima |
| `fig_<p>_e1_memoria.png` | E1: T_cold_total por limite de memória, por runtime |
| `fig_<p>_e2_pacote.png` | E2: pacote mínimo, padrão e ampliado |
| `fig_<p>_e3_rede.png` | E3: rede host × bridge |
| `fig_<p>_e4_cache.png` | E4: cache aquecido × descartado (`drop_caches=3`: page cache e metadados) |
| `fig_<p>_fases.png` | Mediana de cada fase do cold start por configuração |

As figuras são geradas automaticamente a cada execução. Se o CSV não tiver algum experimento, a figura correspondente é pulada com um aviso.

## Cuidados de leitura

- O p99 é exploratório com menos de 100 amostras por configuração.
- Com n pequeno (piloto: 5), o menor p do Mann-Whitney é cerca de 0,008 e a correção de Holm elimina quase tudo; o piloto serve para estimar variabilidade e tamanho de efeito.
- O total ao fim de cada barra em `fig_<p>_fases.png` é a soma das medianas das fases, não a mediana do total.
- Em `T_ready`, só `T_cold_total` é comparável entre runtimes (Node carrega a função ao subir; Python, na 1ª requisição).
- Dados do backend `processo` (sem Docker) recebem marca d'água e não entram em resultados do estudo.