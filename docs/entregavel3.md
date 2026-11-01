# Terceiro entregável: ambiente, coleta automatizada e dados preliminares

Data do piloto: 01/11/2026. Objetivo do marco: provar que o experimento pode ser executado e medido, e identificar problemas metodológicos antes da coleta definitiva. Um piloto anterior (27/10/2026) mostrou as mesmas tendências; este documento usa a rodada de 01/11, feita depois de limpar o repositório e corrigir a análise.

## 1. O que foi comprovado

| Requisito | Evidência |
| --- | --- |
| Ambiente funcionando | `docs/ambiente.md`; 26 configurações iniciam e respondem (130/130 amostras frias válidas) |
| Scripts iniciais | `scripts/` (preparação, imagens, serviços, pacotes, piloto) e `orquestrador/` |
| Execução automatizada | `./scripts/rodar_piloto.sh`: verifica o host, sobe e semeia os serviços, mede e analisa (cerca de 7,5 min para 130 amostras) |
| Coleta de métricas | `t0`, `t_created`, `t_started`, `t_ready`, `t_req`, `t_resp` e `T_cold_total` (relógio monotônico); memória, falhas de página, I/O e OOM pelo cgroup; condições do host por amostra |
| Conjunto preliminar | `resultados/brutos/rodada0_2026-11-01_110508_piloto.csv` (130 frias + 260 quentes) e `.meta.json` |
| Gráficos | `analise/saida/fig_piloto_e1_memoria.png`, `fig_piloto_e2_pacote.png`, `fig_piloto_e3_rede.png`, `fig_piloto_e4_cache.png`, `fig_piloto_fases.png` |

Condições do host durante a rodada: swap em 0 kB, memória disponível acima de 4,7 GB, temperatura entre 58 e 66 °C, frequência entre 2,06 e 3,65 GHz. O orquestrador só inicia a coleta quando o critério ambiental é atendido (ligado na tomada, temperatura até 80 °C, swap 0, RAM mínima de 1,5 GB).

## 2. Execução do piloto

26 configurações (E1: 8, E2: 6, E3: 4, E4: 8), 5 amostras frias cada, com a ordem de todas as amostras embaralhada por semente registrada. A coleta principal (30 amostras × 3 rodadas = 2340) deve levar cerca de 2h15 a 2h30 de máquina quieta.

## 3. Resultados preliminares (mediana de T_cold_total, ms)

| Experimento | Resultado |
| --- | --- |
| E1: memória 128/256/512/1024 MiB | Python 767/769/763/766; Node 724/729/731/745. Sem efeito mensurável (menor p ajustado 0,67): o pico de memória fica bem abaixo do menor limite |
| E2: pacote mínimo/padrão/ampliado (cache aquecido) | Python 691/697/691; Node 738/740/746. Sem efeito com cache aquecido |
| E3: bridge × host | Python 772 × 691 (+81 ms); Node 739 × 646 (+93 ms). Único experimento com p ajustado < 0,05 (0,032) |
| E4: cache descartado × aquecido | A1 Python 1118 × 761 (+358 ms, +47%); A1 Node 1023 × 715 (+307 ms, +43%); A2 Node 1079 × 742 (+337 ms, +45%); A2 Python 998 × 700 (+298 ms, +43%) |

Em E4, as quatro comparações de cache têm efeito grande e o mesmo sentido. Três delas têm p = 0,0079 (o mínimo possível com n = 5); A2 Python tem p = 0,15, porque a configuração aquecida teve dois picos (ver seção 4), apesar da diferença de medianas de ~300 ms.

Outras observações: em média 82% do `T_cold_total` passa antes da prontidão (efeito do `require` do Node ao subir); no Python o SeBS importa a função na primeira requisição (~144 ms), então só `T_cold_total` é comparável entre runtimes. Entre runtimes, o sentido depende da aplicação: em A1 o Node é 30 a 45 ms mais rápido; em A2 com cache aquecido ele é 40 a 55 ms mais lento. As invocações quentes ficam em 3 a 5 ms (A1) e entre 37 e 87 ms (A2).

Limite do piloto: com 5 amostras por configuração o menor p possível do Mann–Whitney é ≈ 0,008. Com a correção de Holm por experimento, só E3 sobrevive a 0,05; em E4 o ajustado fica em 0,0635, valor que o próprio número de testes impõe com n = 5. O piloto estima variabilidade e tamanho de efeito; a inferência fica para as 90 amostras por configuração.

## 4. Problemas metodológicos encontrados

| Problema | Evidência | Ação |
| --- | --- | --- |
| Picos isolados de +300 a +900 ms | 8 de 130 amostras frias (6%): 7 em Python, 1 em Node; em rajadas curtas (pares ou trios a 14–28 s). Acréscimo concentrado em `criar contêiner` (~100 → ~600 ms), `iniciar` (+120 a +165 ms) e `pronto` (~150 → ~345 ms em Python). Temperatura, frequência, memória, swap e falhas de página normais | Causa ainda não identificada. Reportar mediana e IQR; investigar com `strace`/`perf` e logs do sistema na coleta definitiva |
| Coeficiente de variação alto em 6 configurações (29–41%) | `diagnostico_piloto.md`; cada caso tem 1 ou 2 picos | Efeito do n = 5; medianas e IQR continuam estáveis |
| Memória 128–1024 MiB não pressiona a aplicação | Pico de ~38 MB, bem abaixo do menor limite; nenhum OOM | Discutir com o professor níveis menores (por exemplo 32/48/64 MiB) |
| Tamanho do pacote não distingue configurações com cache aquecido | Seção 3 | Cruzar E2 com cache descartado |
| Critério ambiental bloqueou a coleta | Swap em 3 GB e RAM livre de 1 GB antes da rodada; orquestrador esperou 300 s e abortou | Funcionou como previsto; foi preciso reiniciar a máquina. Registrar como pré-condição do protocolo |
| Swap em zram persiste após `swapoff -a` | `swapon --show` lista `/dev/zram0` | Desativar o zram de forma persistente antes da coleta principal; uso de swap já é checado em 0 kB |
| `drop_caches=3` descarta page cache, dentries e inodes de todo o host | Também esfria ScyllaDB e Minio | Discutir com o professor; documentar como "descarte combinado" |
| Imagens-base sem versão fixa | `python:3.11-slim`, `ubuntu:22.04`, `chainguard/minio:latest` | Registrar versões efetivas no meta; congelar por digest antes da coleta principal |
| Pacotes não equivalentes entre runtimes (A2 Python 233 arquivos/15,6 MB; Node 5633 arquivos/197 MB) | `construir_pacote.py` | Registrar como limitação; comparar runtimes só por `T_cold_total` |
| `strace` e `perf` ainda não instalados nem usados | `00_verificar_host.sh` | Instalar (`brew` ou `rpm-ostree`) e implementar o subconjunto instrumentado |
| Imagem de execução do Node do SeBS quebrada: `ENV PATH` usa `$(...)` e `NODE_PATH` aponta para diretório inexistente | Contêiner saía com código 127 e depois 1 | Camada fina `configs/patches/nodejs-path.Dockerfile`, aplicada por `scripts/construir_imagens.sh` |
| Módulo nativo `sharp` compilado no host exige glibc 2.38; o contêiner tem 2.35 | `GLIBC_2.38 not found` | `npm install` do Node roda dentro da imagem de execução |
| Imagens de execução do SeBS não existem no Docker Hub | `pull access denied` | Construção local a partir dos submódulos |
| Imagem do Minio removida do Docker Hub | `docker pull` falhou | Imagem Chainguard congelada como `cs-minio:fixed` |
| Docker 29 removeu `NetworkSettings.IPAddress` | Scripts de serviços falhavam | Uso de `Networks.bridge.IPAddress` |
| Serviços (ScyllaDB, Minio) não sobrevivem a reinício | Falha de requisição do A2 após uma semana | `rodar_piloto.sh` sobe e semeia sempre |
| O orquestrador abortava em falhas de aquecimento e perdia o log do contêiner | Piloto interrompido na primeira configuração com erro | Falha vira linha `falha_inicio`; logs em `resultados/falhas/` |

