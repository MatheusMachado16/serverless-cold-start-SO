# Marco preliminar: ambiente, scripts e experimentos piloto

Estado em 17/10/2026. Este documento separa o que foi **testado** do que está **escrito mas ainda não foi executado no notebook**, para não apresentar como resultado o que ainda é plano.

## Situação dos entregáveis

| Entregável | Situação | Evidência / onde |
| --- | --- | --- |
| Ambiente funcionando | **Escrito, não testado com Docker.** Scripts de verificação do host, preparação (SeBS no commit fixado, imagens, pacotes) e serviços (ScyllaDB, Minio). | `scripts/00_verificar_host.sh`, `01_preparar.sh`, `servicos.sh`, `semear_servicos.py` |
| Scripts iniciais | **Prontos.** Orquestrador, coletores, construtor de pacotes e análise. Testados: orquestrador e análise (backend sem Docker), construtor de pacotes (A1 e A2 em Python, A1 em Node, controle), montagem do `docker create` (rede `bridge` e `host`, memória, swap, CPU) e tratamento de falhas. | `orquestrador/`, `scripts/construir_pacote.py`, `analise/analisar.py` |
| Execução automatizada | **Pronta.** Uma rodada completa é um comando; as 26 configurações com agenda sorteada em blocos, `seed` registrada e CSV que nunca sobrescreve. Agenda conferida com `--dry-run` (130 amostras no piloto). | `scripts/rodar_piloto.sh`, `orquestrador/run_experimento.py` |
| Coleta de métricas | **Parcial.** Coleta: tempos `T_cold_total`, `T_ready`, `T_req_cold`, criação e início do contêiner, quentes, validação de saída, cgroups v2 (CPU, memória atual/pico, `oom_kill`, falhas de página totais/major/minor, I/O), `docker events` (opcional) e condições do host. **Ainda não implementados:** `strace` e `perf stat` (subconjunto instrumentado). | `orquestrador/coletores.py`, colunas em `resultados/README.md` |
| Conjunto preliminar de dados | **Pendente para dados reais.** Só existe a rodada de validação do pipeline, que usa processos comuns em vez de contêineres e **não vale como dado do estudo**. O conjunto real sai de `./scripts/rodar_piloto.sh` no notebook. | `resultados/validacao_pipeline/` (validação), `resultados/brutos/` (vazio até o piloto) |
| Pelo menos um gráfico | **Gerado com os dados de validação** (marca d'água avisa). Regerado automaticamente com os dados reais pelo mesmo script. | `analise/saida/fig_smoke_*.png` |

## O que o teste do pipeline já mostrou

Rodada `resultados/validacao_pipeline/` (80 frios e 60 quentes; controle `010.sleep`; duas configurações idênticas, para medir o ruído do próprio método). Resumo em `analise/saida/diagnostico_smoke.md`.

- O pipeline mede, valida, grava e analisa de ponta a ponta. Amostras inválidas viram linha com o motivo.
- O teste A/A deu diferença de ~1 ms entre configurações idênticas (p ≈ 0,07), com CV ≈ 9%. Serve de piso de ruído.
- A leitura do código do SeBS revelou **sete pontos que afetam a interpretação** das métricas (A1 a A7 em `docs/protocolo.md`). Os mais importantes: o Python importa a aplicação na primeira requisição e o Node ao subir (então só `T_cold_total` compara os runtimes), e o `entrypoint.sh` do SeBS executa `useradd`/`chown` em todo início de contêiner (custo fixo dentro do tempo medido).

## Como executar no notebook

```bash
# 1. verificar o host e registrar o ambiente
./scripts/00_verificar_host.sh          # gera docs/ambiente_coletado.txt; copie para docs/ambiente.md
sudo cpupower frequency-set -g performance

# 2. preparar (fora da medição): SeBS no commit b37f475, imagens, pacotes
./scripts/01_preparar.sh                # padrão: ~/serverless-benchmarks

# 3. piloto completo: serviços, semeadura, 26 configs x 5 frios, análise
sudo -E ./scripts/rodar_piloto.sh       # sudo só é necessário para o drop_caches de E4

# resultados:  resultados/brutos/rodada0_*.csv
#              analise/saida/diagnostico_piloto.md  e  fig_piloto_*.png
```

Para ensaiar antes com poucas amostras: `python3 orquestrador/run_experimento.py --filtro 'E1-py' --n-frio 3 --n-quente 5 --tag ensaio`.

## Riscos conhecidos (o que pode falhar na primeira execução)

Os scripts que falam com Docker, ScyllaDB e Minio nunca rodaram. Os pontos mais prováveis de ajuste:

- Nome/versão das imagens (`spcleth/serverless-benchmarks:run.local.python.3.11`, `...nodejs.20`) e a versão do ScyllaDB (`SCYLLA_VERSION`, padrão 6.2, escolha minha, não do SeBS).
- Variáveis de ambiente do Minio (as imagens recentes usam `MINIO_ROOT_USER`; o script define as duas formas).
- O caminho do cgroup do contêiner e a presença de `memory.peak` (o diagnóstico acusa métricas vazias).
- A semeadura de A2 depende das imagens em `benchmarks-data/` do clone do SeBS e do Pillow no host.
- Se `docker create`/`start` via CLI custar muito dentro de `t0`, trocar pela API do Docker (decisão 11 do protocolo).

## Falta para fechar o marco

1. Rodar o piloto no notebook e conferir o diagnóstico (métricas preenchidas, `docker inspect` batendo com o configurado, A1 e A2 válidas em Python e Node).
2. Implementar `strace` e `perf stat` no subconjunto instrumentado (anexar ao PID do contêiner logo após o `start`; registrar a janela parcial).
3. Preencher `docs/ambiente.md` e as decisões 1 a 14 de `docs/protocolo.md` com a evidência do piloto.
4. Discutir com o professor os itens 7 e A3 (descarte combinado de caches; o custo fixo do `entrypoint.sh` entra ou não em cold start).
