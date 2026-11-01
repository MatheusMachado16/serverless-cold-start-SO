# resultados

| Pasta | Conteúdo |
| --- | --- |
| `brutos/` | Dados reais do estudo: um CSV e um `.meta.json` por rodada, com nome `rodadaN_AAAA-MM-DD_HHMMSS_tag.csv`. Nunca sobrescrever nem editar. A análise lê **todos** os CSVs desta pasta, então testes e ensaios não devem ficar aqui |
| `falhas/` | Últimas linhas do log de contêineres que caíram durante a coleta (evidência de problemas de ambiente) |
| `rastros/` | Eventos do Docker por amostra (não versionados) |

O `.meta.json` de cada rodada guarda a semente, os parâmetros e o snapshot do ambiente (versões de sistema, kernel e Docker, imagens, swap, governador).

## Colunas principais do CSV

A lista completa está na primeira linha de cada arquivo. Métrica indisponível vira célula vazia, nunca 0.

- identificação: `config_id`, `exp`, `amostra_id`, `rodada`, `repeticao`, `tipo` (`frio` ou `quente`), `validacao` e `motivo`;
- fatores da configuração: `workload`, `runtime`, `pacote`, `mem_mib`, `rede`, `cache`;
- tempos em ms: `t_created_ms`, `t_started_ms`, `t_ready_ms`, `t_req_cold_ms`, `t_cold_total_ms` (e `lat_req_ms` nas invocações quentes);
- cgroup: `mem_pico_bytes`, `pgmajfault`, `io_rbytes`, `oom_kill`, `oom_flag`;
- configuração efetiva: `mem_efetiva_bytes`, `rede_efetiva`, `swap_efetivo_bytes`, `nano_cpus`, `cache_nivel`;
- condições do host antes da amostra: colunas `host_*` (temperatura, frequência, memória disponível, swap, tomada, governador).

Resultados e figuras: `../analise/saida/`.