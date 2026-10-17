# Diagnóstico — piloto

Arquivos: rodada1_2026-10-17_183743_smoke.csv

Amostras: 80 frias (80 válidas), 60 quentes.

## Achados

- **ATENÇÃO** — Há dados do backend `processo` (sem Docker). Servem para validar o pipeline; NÃO são cold start de contêiner e não devem entrar em resultados do estudo.
- **OK** — Todas as 80 amostras frias foram válidas (resposta 200 e saída validada).
- **ATENÇÃO** — SMOKE-aa-1: latência correlacionada com a ordem de execução (Spearman rho=-0.37, p=0.018) — possível deriva térmica/de cache (vários testes: p não corrigido).
- **INFO** — Amostras frias necessárias para IC95% da média com ±5% de precisão: mediana entre configs = 11, máximo = 12 (plano: 90 por configuração).
- **INFO** — Fração mediana do T_cold_total gasta até a prontidão: 59% (o restante é a primeira requisição).
- **INFO** — Python: o SeBS importa a função DENTRO da 1ª requisição (srv_import_ms mediano = 0.37 ms). Assim `T_ready` não inclui o import da aplicação em Python, mas inclui em Node.js (que faz `require` ao subir). Só `T_cold_total` é comparável entre runtimes.
- **INFO** — Intervalo entre t_ready e t_req: mediana 0.02 ms, máx 0.17 ms (sondagem a cada 5 ms).
- **INFO** — Teste A/A (SMOKE-aa-1 x SMOKE-aa-2, configs idênticas): diferença de medianas = +0.8 ms, p = 0.073. Diferença não detectada com este n (isso não prova ausência de viés; serve de piso de ruído).
- **ATENÇÃO** — Métricas sem nenhuma observação (registradas como ausentes): io_rbytes, host_temp_c, host_freq_khz
- **ATENÇÃO** — Sem leitura de temperatura/tomada: os critérios ambientais não puderam ser verificados nesta máquina.

## Resumo por configuração (ms)

| config_id   |   n |   mediana |   ic95_med_lo |   ic95_med_hi |   media |    dp |   cv |   iqr |    p95 |    p99 |   ready_mediana |   quente_mediana |   overhead_mediana |
|:------------|----:|----------:|--------------:|--------------:|--------:|------:|-----:|------:|-------:|-------:|----------------:|-----------------:|-------------------:|
| SMOKE-aa-1  |  40 |    125.51 |        124.72 |        128.69 |  128.56 | 11.02 | 0.09 | 10.45 | 149.25 | 153.11 |           73.67 |            51.35 |              74.16 |
| SMOKE-aa-2  |  40 |    124.67 |        124.3  |        125.26 |  124.28 |  9.77 | 0.08 | 10.2  | 141.35 | 144.88 |           73.08 |            51.36 |              73.31 |

## Comparações (Mann–Whitney, correção de Holm)

| exp   | a          | b          |   dif_mediana_ms |   efeito_rbc |      p |   p_holm |   kruskal_p |
|:------|:-----------|:-----------|-----------------:|-------------:|-------:|---------:|------------:|
| SMOKE | SMOKE-aa-1 | SMOKE-aa-2 |           0.8428 |      -0.2337 | 0.0727 |   0.0727 |         nan |

_p99 é exploratório com menos de 100 amostras por configuração._
