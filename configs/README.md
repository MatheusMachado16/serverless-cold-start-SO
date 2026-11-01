# configs

Configurações dos experimentos, do ambiente local e dos critérios de coleta.

## Experimentos

| Arquivo | Experimento | Configurações |
| --- | --- | --- |
| `e1_runtime_memoria.json` | E1: runtime × limite de memória (A1, pacote padrão, `bridge`, cache aquecido) | 8 |
| `e2_pacote.json` | E2: pacote mínimo, padrão e ampliado (A2, 256 MiB, `bridge`, cache aquecido) | 6 |
| `e3_rede.json` | E3: `bridge` × `host` (A1, 256 MiB, pacote padrão, cache aquecido) | 4 |
| `e4_cache.json` | E4: cache aquecido × descartado (A1 e A2, 256 MiB, pacote padrão, `bridge`) | 8 |
| `controle.json` | CTRL: microbenchmark `010.sleep`, fora das 26 configurações principais | 2 |
| `smoke.json` | SMOKE: teste A/A do pipeline, duas configurações idênticas; não é experimento do estudo | 2 |

Cada configuração tem `id`, `workload`, `runtime`, `mem_mib`, `pacote`, `rede` e `cache`. O ID do experimento é preservado em todos os registros.

Algumas condições de referência coincidem entre grupos e têm IDs diferentes: `E1-*-256`, `E3-*-bridge` e `E4-a1-*-aque` são a mesma configuração, assim como `E2-*-padrao` e `E4-a2-*-aque`. São 26 configurações, não 26 combinações únicas.

## Ambiente e critérios

| Arquivo | Conteúdo |
| --- | --- |
| `ambiente_local.json` | Caminho do SeBS, imagens por runtime, CPU, timeouts e variáveis de ambiente por workload. **Reescrito por `scripts/01_preparar.sh` e `scripts/semear_servicos.py`** (caminho do SeBS, IPs dos serviços); o caminho padrão do SeBS é `~/serverless-benchmarks` |
| `criterios.json` | Critérios ambientais que pausam ou interrompem a coleta (tomada, temperatura, swap, RAM disponível). Valores provisórios; ver `docs/protocolo.md` |
| `workloads.json` | Benchmark do SeBS e evento de entrada de cada workload (CTRL, A1, A2) |

## Subpastas

| Pasta | Conteúdo |
| --- | --- |
| `eventos/` | Entradas das requisições. `a1_small.json` e `a2.json` são **gerados por `scripts/semear_servicos.py`** (novo ID de carrinho em A1 a cada execução); `a2.meta.json` registra o hash da imagem de A2 |
| `patches/` | Alterações locais na imagem do SeBS: `nodejs-path.Dockerfile` corrige `PATH` e `NODE_PATH` da imagem do Node. Parte da imagem original do SeBS etiquetada como `cs-sebs-node-base:orig` |