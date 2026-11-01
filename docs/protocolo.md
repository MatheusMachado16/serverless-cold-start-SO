# Protocolo: decisões do piloto e critérios de validação

Cada item da seção 12 do README vira aqui uma decisão registrada: a decisão, a evidência e a data. As decisões abaixo são **provisórias**: valem para o piloto (01/11/2026) e serão confirmadas ou revistas antes da coleta definitiva.

| # | O que precisa ser decidido | Como o piloto valida | Decisão |
| --- | --- | --- | --- |
| 1 | O ambiente local com Docker e a definição de cold start (`t0` até `t_resp`) são adequados | 5 cold starts por configuração; conferir se `T_cold_total` é estável e interpretável | provisória: adequado (ver resultado) |
| 2 | A1 (`130.crud-api`) e A2 (`210.thumbnailer`) funcionam e são equivalentes em Python e Node.js | Mesma entrada nos dois runtimes; comparar a saída e o que é gravado no ScyllaDB e no Minio | provisória: funcionam; equivalência das saídas pendente |
| 3 | Limites de memória de 128 e 256 MiB são viáveis | Verificar OOM com `docker inspect` e `memory.events` | provisória: viáveis, mas não pressionam a aplicação |
| 4 | Quais patches no SeBS são necessários (`mem_limit`, `network_mode`) | `docker inspect` do contêiner criado: conferir limite e rede reais. *Observação inicial no commit `b37f475`: `sebs/local/local.py` fixa `network_mode: "bridge"` e não define `mem_limit`; confirmar no piloto.* | provisória: só a camada do Node |
| 5 | Como são os pacotes mínimo, padrão e ampliado, e o que é só presente × realmente importado | Medir tamanho, número de arquivos e arquivos abertos (`strace`) em cada pacote | parcial: tamanho e arquivos medidos; `strace` pendente |
| 6 | Prontidão sem executar a carga antes da requisição medida; instrumentação cobre o início do runtime | Sondagem HTTP a cada 5 ms até a primeira resposta; checar nos rastros que o handler não rodou antes de `t_req` | parcial: sondagem validada; rastros pendentes |
| 7 | Descarte combinado de caches (`drop_caches=3`) é aceito; interesse em análise com `=1` | Discutir com o professor | provisória: aceito; discutir com o professor |
| 8 | Quantidade de repetições, critérios ambientais que interrompem a coleta e tamanho do subconjunto instrumentado | Variabilidade (CV, IC) do piloto; limites de temperatura, swap e frequência | provisória: 30 × 3 rodadas; critérios mantidos |

## Critérios ambientais de interrupção (valores provisórios de `configs/criterios.json`)

| Variável | Limite | Ferramenta |
| --- | --- | --- |
| Temperatura da CPU | interromper acima de 80 °C | `sensors` |
| Atividade de swap | interromper se o uso for maior que 0 kB | `vmstat` |
| RAM disponível | interromper abaixo de 1,5 GB disponíveis | `free` |
| Notebook fora da tomada | interromper a coleta | — |

## Resultado do piloto (01/11/2026)

Dados: `resultados/brutos/rodada0_2026-11-01_110508_piloto.csv`. Detalhes em `docs/entregavel3.md`. Um piloto anterior (27/10/2026) mostrou as mesmas tendências.

1. **Ambiente e definição de cold start: adequados.** 130/130 amostras frias válidas, 7,5 min de execução. Coeficiente de variação: 18 das 26 configurações com CV ≤ 3%, 2 entre 4% e 5%, e 6 entre 29% e 41%, cada uma com 1 ou 2 picos (item 8 de `entregavel3.md`, seção 4). A causa dos picos ainda não foi identificada; a mediana e o IQR permanecem estáveis.
2. **A1 e A2 funcionam em Python e Node.js**, após os patches descritos em `docs/entregavel3.md` (seção 4). A comparação direta das saídas entre runtimes ainda está pendente.
3. **Limites de memória:** 128 e 256 MiB são viáveis (nenhuma amostra com OOM), mas o pico de ~38 MB fica bem abaixo de todos os níveis testados e E1 não mostra efeito (menor p ajustado 0,67). Decisão pendente: discutir com o professor níveis menores (por exemplo 32/48/64 MiB) para que a memória realmente limite a aplicação.
4. **Patches no SeBS:** apenas a camada do Node (`configs/patches/nodejs-path.Dockerfile`); `mem_limit` e `network_mode` são definidos pelo orquestrador no `docker create`.
5. **Pacotes:** diferenças de arquivos e tamanho em `construir_pacote.py` (A2 Python 233 arquivos/15,6 MB; Node 5633 arquivos/197 MB, não equivalentes). Com cache aquecido o tamanho do pacote não altera o cold start (E2); falta medir arquivos abertos com `strace` e cruzar E2 com cache descartado.
6. **Prontidão:** detectada por sondagem a cada 5 ms; intervalo `t_ready` a `t_req` com mediana de 0,03 ms e máximo de 0,06 ms. Falta confirmar nos rastros que o handler não executa antes de `t_req`.
7. **`drop_caches=3`:** aceito provisoriamente. Descartar os caches aumentou o cold start em 43% a 47% (+298 a +358 ms). O descarte também esfria ScyllaDB e Minio; discutir com o professor e avaliar `=1`.
8. **Repetições e critérios ambientais:** manter 30 por rodada × 3 rodadas; picos tratados com mediana e IQR. Os critérios ambientais funcionaram: antes da rodada o orquestrador bloqueou a coleta (swap de 3 GB e 1 GB de RAM livre) e foi preciso reiniciar a máquina. Durante a rodada: swap 0 kB, RAM disponível acima de 4,7 GB, temperatura de 58 a 66 °C. A estimativa de amostras necessárias só pode ser calculada com 30 amostras por configuração.