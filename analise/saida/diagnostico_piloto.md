# Diagnóstico — piloto

Arquivos: rodada0_2026-11-01_110508_piloto.csv

Amostras: 130 frias (130 válidas), 260 quentes.

## Achados

- **OK** — Todas as 130 amostras frias foram válidas (resposta 200 e saída validada).
- **ATENÇÃO** — E2-py-minimo: CV = 29%; variabilidade alta (com n pequeno, um único pico já provoca isso).
- **ATENÇÃO** — E1-py-128: CV = 41%; variabilidade alta (com n pequeno, um único pico já provoca isso).
- **ATENÇÃO** — E2-py-padrao: CV = 35%; variabilidade alta (com n pequeno, um único pico já provoca isso).
- **ATENÇÃO** — E2-js-minimo: CV = 35%; variabilidade alta (com n pequeno, um único pico já provoca isso).
- **ATENÇÃO** — E4-a2-py-aque: CV = 39%; variabilidade alta (com n pequeno, um único pico já provoca isso).
- **ATENÇÃO** — E1-py-1024: CV = 38%; variabilidade alta (com n pequeno, um único pico já provoca isso).
- **INFO** — Estimativa de amostras necessárias não calculada: com n < 30 por configuração o desvio padrão é instável. Recalcular com a rodada 1 (30 por configuração).
- **INFO** — Fração mediana do T_cold_total gasta até a prontidão: 82% (o restante é a primeira requisição).
- **INFO** — Python: o SeBS importa a função DENTRO da 1ª requisição (srv_import_ms mediano = 144.30 ms). Assim `T_ready` não inclui o import da aplicação em Python, mas inclui em Node.js (que faz `require` ao subir). Só `T_cold_total` é comparável entre runtimes.
- **INFO** — Intervalo entre t_ready e t_req: mediana 0.03 ms, máx 0.06 ms (sondagem a cada 5 ms).

## Resumo por configuração (ms)

| config_id      |   n |   mediana |   ic95_med_lo |   ic95_med_hi |   media |     dp |   cv |    iqr |     p95 |     p99 |   ready_mediana |   quente_mediana |   overhead_mediana |
|:---------------|----:|----------:|--------------:|--------------:|--------:|-------:|-----:|-------:|--------:|--------:|----------------:|-----------------:|-------------------:|
| E1-py-256      |   5 |    768.6  |        766.57 |        796.09 |  776.35 |  12.84 | 0.02 |  14.92 |  793.41 |  795.55 |          464.02 |             3.06 |             765.54 |
| E3-js-bridge   |   5 |    738.77 |        707.95 |        779.54 |  735.51 |  29.01 | 0.04 |  30.45 |  771.8  |  777.99 |          686.16 |             4.17 |             734.6  |
| E3-js-host     |   5 |    645.68 |        618.91 |        656.53 |  640.11 |  15.04 | 0.02 |  17.59 |  654.92 |  656.2  |          612.24 |             4    |             641.69 |
| E2-py-ampliado |   5 |    691.04 |        686.67 |        694.43 |  690.91 |   2.91 | 0    |   2.6  |  694.05 |  694.36 |          459.53 |            37.07 |             653.96 |
| E1-js-256      |   5 |    728.97 |        718.13 |        747.82 |  731.04 |  12.89 | 0.02 |  20.54 |  746.34 |  747.52 |          699.98 |             4.24 |             724.73 |
| E4-a2-js-desc  |   5 |   1078.71 |       1066.37 |       1138.89 | 1089.01 |  28.57 | 0.03 |   5.05 | 1127.73 | 1136.66 |          983.48 |            81.08 |             997.63 |
| E3-py-host     |   5 |    690.68 |        680.32 |        766.56 |  702.12 |  36.46 | 0.05 |  12.08 |  751.76 |  763.6  |          385.27 |             2.71 |             687.97 |
| E2-py-minimo   |   5 |    691.24 |        683.62 |       1217.88 |  801.22 | 233.46 | 0.29 |  34.8  | 1119.12 | 1198.13 |          458.86 |            37.07 |             654.17 |
| E1-js-128      |   5 |    724.13 |        717.67 |        726.02 |  722.83 |   3.34 | 0    |   3.45 |  725.79 |  725.97 |          696.94 |             4.69 |             719.44 |
| E1-py-128      |   5 |    767.22 |        764.8  |       1627.61 |  940.65 | 384.06 | 0.41 |  12.39 | 1457.69 | 1593.62 |          462.43 |             2.89 |             764.33 |
| E4-a1-js-desc  |   5 |   1022.82 |       1012.62 |       1036.08 | 1022.33 |   8.85 | 0.01 |   6.26 | 1033.5  | 1035.56 |          996.11 |             4.55 |            1018.27 |
| E4-a1-py-aque  |   5 |    760.71 |        760.39 |        771.54 |  764.12 |   5.1  | 0.01 |   6.84 |  770.71 |  771.38 |          457.47 |             3.2  |             757.51 |
| E1-py-512      |   5 |    762.97 |        755.41 |        769.84 |  763.48 |   5.58 | 0.01 |   5.68 |  769.36 |  769.74 |          454.84 |             3.08 |             759.89 |
| E3-py-bridge   |   5 |    772.17 |        767.36 |        786.07 |  773.51 |   7.53 | 0.01 |   5.69 |  783.62 |  785.58 |          463.52 |             3.09 |             769.09 |
| E2-py-padrao   |   5 |    696.59 |        680.28 |       1333.75 |  818.75 | 287.98 | 0.35 |  10.48 | 1206.36 | 1308.27 |          462.25 |            36.69 |             659.9  |
| E4-a2-js-aque  |   5 |    741.91 |        724.92 |        753.3  |  739.28 |  13.67 | 0.02 |  25.89 |  752.86 |  753.21 |          626.24 |            83.04 |             658.87 |
| E1-js-1024     |   5 |    745.47 |        721.54 |        755.84 |  743.81 |  13.19 | 0.02 |   5.58 |  754.85 |  755.64 |          703.19 |             4.1  |             741.37 |
| E1-js-512      |   5 |    730.89 |        713    |        751.97 |  730.84 |  14.82 | 0.02 |  14.69 |  748.88 |  751.35 |          692.16 |             4.31 |             726.59 |
| E2-js-padrao   |   5 |    739.65 |        721.94 |        748.7  |  737.1  |  10.26 | 0.01 |   9.96 |  747.48 |  748.46 |          632.54 |            77.76 |             661.89 |
| E4-a1-py-desc  |   5 |   1118.46 |       1108.27 |       1143.6  | 1124.7  |  14.26 | 0.01 |  16.77 | 1141.87 | 1143.26 |          659.33 |             2.81 |            1115.65 |
| E4-a1-js-aque  |   5 |    715.35 |        696.98 |        745.69 |  722.73 |  20.89 | 0.03 |  29.95 |  745.11 |  745.58 |          692.31 |             4.19 |             711.16 |
| E2-js-minimo   |   5 |    738.31 |        721.85 |       1421.43 |  870.54 | 308.08 | 0.35 |  17.57 | 1286.01 | 1394.34 |          612.41 |            87.51 |             650.8  |
| E4-a2-py-desc  |   5 |    997.85 |        930.72 |       1013.55 |  988.8  |  33.22 | 0.03 |  10.22 | 1012.05 | 1013.25 |          656.8  |            38.09 |             959.77 |
| E4-a2-py-aque  |   5 |    700.12 |        682.54 |       1488.27 |  892.26 | 344.52 | 0.39 | 198.91 | 1369.55 | 1464.53 |          466.64 |            37.3  |             662.81 |
| E1-py-1024     |   5 |    766.49 |        755.3  |       1640.51 | 1003.66 | 383.69 | 0.38 | 328.34 | 1530.84 | 1618.58 |          458.31 |             3.06 |             763.43 |
| E2-js-ampliado |   5 |    746.33 |        737.7  |        755.4  |  746.26 |   6.28 | 0.01 |   0.92 |  753.6  |  755.04 |          633.63 |            77.85 |             668.48 |

## Comparações (Mann–Whitney entre configurações que diferem em um fator; Holm por experimento)

| exp   | fator   | a              | b              |   dif_mediana_ms |   efeito_rbc |      p |   p_holm |   kruskal_p |
|:------|:--------|:---------------|:---------------|-----------------:|-------------:|-------:|---------:|------------:|
| E1    | mem_mib | E1-js-1024     | E1-js-128      |          21.3395 |        -0.76 | 0.0556 |   0.6667 |      0.1777 |
| E1    | mem_mib | E1-js-1024     | E1-js-256      |          16.4953 |        -0.6  | 0.1508 |   1      |      0.1777 |
| E1    | mem_mib | E1-js-1024     | E1-js-512      |          14.5744 |        -0.44 | 0.3095 |   1      |      0.1777 |
| E1    | runtime | E1-js-1024     | E1-py-1024     |         -21.0199 |         0.92 | 0.0159 |   0.2063 |    nan      |
| E1    | mem_mib | E1-js-128      | E1-js-256      |          -4.8442 |         0.36 | 0.4206 |   1      |      0.1777 |
| E1    | mem_mib | E1-js-128      | E1-js-512      |          -6.7651 |         0.36 | 0.4206 |   1      |      0.1777 |
| E1    | runtime | E1-js-128      | E1-py-128      |         -43.0878 |         1    | 0.0079 |   0.127  |    nan      |
| E1    | mem_mib | E1-js-256      | E1-js-512      |          -1.9209 |         0.04 | 1      |   1      |      0.1777 |
| E1    | runtime | E1-js-256      | E1-py-256      |         -39.6281 |         1    | 0.0079 |   0.127  |    nan      |
| E1    | runtime | E1-js-512      | E1-py-512      |         -32.0738 |         1    | 0.0079 |   0.127  |    nan      |
| E1    | mem_mib | E1-py-1024     | E1-py-128      |          -0.7284 |         0.12 | 0.8413 |   1      |      0.3512 |
| E1    | mem_mib | E1-py-1024     | E1-py-256      |          -2.1129 |         0.2  | 0.6905 |   1      |      0.3512 |
| E1    | mem_mib | E1-py-1024     | E1-py-512      |           3.5205 |        -0.28 | 0.5476 |   1      |      0.3512 |
| E1    | mem_mib | E1-py-128      | E1-py-256      |          -1.3844 |         0.28 | 0.5476 |   1      |      0.3512 |
| E1    | mem_mib | E1-py-128      | E1-py-512      |           4.2489 |        -0.52 | 0.2222 |   1      |      0.3512 |
| E1    | mem_mib | E1-py-256      | E1-py-512      |           5.6334 |        -0.68 | 0.0952 |   1      |      0.3512 |
| E2    | pacote  | E2-js-ampliado | E2-js-minimo   |           8.016  |        -0.44 | 0.3095 |   1      |      0.3396 |
| E2    | pacote  | E2-js-ampliado | E2-js-padrao   |           6.677  |        -0.52 | 0.2222 |   1      |      0.3396 |
| E2    | runtime | E2-js-ampliado | E2-py-ampliado |          55.2902 |        -1    | 0.0079 |   0.0714 |    nan      |
| E2    | pacote  | E2-js-minimo   | E2-js-padrao   |          -1.339  |         0.04 | 1      |   1      |      0.3396 |
| E2    | runtime | E2-js-minimo   | E2-py-minimo   |          47.0691 |        -0.6  | 0.1508 |   1      |    nan      |
| E2    | runtime | E2-js-padrao   | E2-py-padrao   |          43.0611 |        -0.6  | 0.1508 |   1      |    nan      |
| E2    | pacote  | E2-py-ampliado | E2-py-minimo   |          -0.2052 |         0.12 | 0.8413 |   1      |      0.8869 |
| E2    | pacote  | E2-py-ampliado | E2-py-padrao   |          -5.5521 |         0.2  | 0.6905 |   1      |      0.8869 |
| E2    | pacote  | E2-py-minimo   | E2-py-padrao   |          -5.347  |        -0.04 | 1      |   1      |      0.8869 |
| E3    | rede    | E3-js-bridge   | E3-js-host     |          93.0893 |        -1    | 0.0079 |   0.0317 |    nan      |
| E3    | runtime | E3-js-bridge   | E3-py-bridge   |         -33.4018 |         0.68 | 0.0952 |   0.0952 |    nan      |
| E3    | runtime | E3-js-host     | E3-py-host     |         -44.9966 |         1    | 0.0079 |   0.0317 |    nan      |
| E3    | rede    | E3-py-bridge   | E3-py-host     |          81.4945 |        -1    | 0.0079 |   0.0317 |    nan      |
| E4    | cache   | E4-a1-js-aque  | E4-a1-js-desc  |        -307.478  |         1    | 0.0079 |   0.0635 |    nan      |
| E4    | runtime | E4-a1-js-aque  | E4-a1-py-aque  |         -45.3604 |         1    | 0.0079 |   0.0635 |    nan      |
| E4    | runtime | E4-a1-js-desc  | E4-a1-py-desc  |         -95.635  |         1    | 0.0079 |   0.0635 |    nan      |
| E4    | cache   | E4-a1-py-aque  | E4-a1-py-desc  |        -357.753  |         1    | 0.0079 |   0.0635 |    nan      |
| E4    | cache   | E4-a2-js-aque  | E4-a2-js-desc  |        -336.801  |         1    | 0.0079 |   0.0635 |    nan      |
| E4    | runtime | E4-a2-js-aque  | E4-a2-py-aque  |          41.7907 |        -0.2  | 0.6905 |   0.6905 |    nan      |
| E4    | runtime | E4-a2-js-desc  | E4-a2-py-desc  |          80.8567 |        -1    | 0.0079 |   0.0635 |    nan      |
| E4    | cache   | E4-a2-py-aque  | E4-a2-py-desc  |        -297.735  |         0.6  | 0.1508 |   0.3016 |    nan      |

_p99 é exploratório com menos de 100 amostras por configuração._
