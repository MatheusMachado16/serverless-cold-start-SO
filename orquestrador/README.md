# orquestrador

Executa a coleta: cria um contêiner por amostra fria, mede as fases do cold start, faz as invocações quentes e grava tudo em CSV. Uma rodada ordena todas as amostras de todas as configurações em sequência embaralhada por uma semente registrada.

## Arquivos

| Arquivo | Função |
| --- | --- |
| `run_experimento.py` | Linha de comando: monta a agenda (ordem embaralhada em blocos), confere os critérios ambientais antes de cada amostra, grava o CSV e o `.meta.json` da rodada |
| `medir.py` | Uma amostra fria (`docker create` com limites, `start`, espera de prontidão por sondagem a cada 5 ms, 1ª requisição, validação da saída) e as invocações quentes no mesmo contêiner |
| `backends.py` | `BackendDocker` (usado no estudo) e `BackendProcesso` (só valida o pipeline sem Docker; os dados recebem marca d'água e não são resultado do estudo). Guarda o log de contêineres que caem em `resultados/falhas/` |
| `coletores.py` | Condições do host (temperatura, frequência, tomada, memória e swap), leitura do cgroup v2 e do `/proc`, `docker events` e descarte de caches (`drop_caches`) |

## Uso

```bash
# ver a agenda sem executar nada
python3 orquestrador/run_experimento.py --configs configs/e1_runtime_memoria.json --n-frio 5 --dry-run

# piloto: 26 configurações, 5 frios e 10 quentes cada
python3 orquestrador/run_experimento.py --piloto --rodada 0 --eventos

# rodada da coleta principal: 30 frios e 50 quentes por configuração
python3 orquestrador/run_experimento.py --rodada 1 --eventos
```

Opções úteis: `--filtro REGEX` (só as configurações cujo id casa), `--seed`, `--tag` (rótulo no nome do arquivo), `--drop-nivel` (padrão 3). O E4 com cache descartado exige `sudo` sem senha ou rodar como root.

Quase sempre você vai usar `./scripts/rodar_piloto.sh`, que também sobe os serviços, semeia os dados e roda a análise.

## Saída

`resultados/brutos/rodadaN_AAAA-MM-DD_HHMMSS_tag.csv` e o `.meta.json` correspondente, com a semente, os parâmetros e o snapshot do ambiente. As colunas estão descritas em `resultados/README.md`. Métrica indisponível vira célula vazia, nunca 0.

## Ainda não implementado

`strace` e `perf stat` (subconjunto instrumentado): ver `docs/entregavel3.md`, seção 5.