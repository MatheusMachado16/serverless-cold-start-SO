# orquestrador

Script em Python que executa cada medição: remove o contêiner anterior, cria um novo (`sebs local start`), envia a requisição, mede o tempo com `time.perf_counter_ns` e grava a amostra em CSV.

Arquivos previstos:

- `run_experimento.py`: percorre as configurações da rodada em ordem sorteada
- `medir.py`: uma medição a frio e as 50 medições quentes
- `coletores.py`: `docker events`, cgroups, `strace` e `perf stat`
