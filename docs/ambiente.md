# Registro do ambiente

Valores medidos no piloto de 27/10/2026. Reconferir antes de cada rodada (o Bluefin se atualiza sozinho: kernel, Docker e imagem do sistema podem mudar entre as rodadas). A saída bruta do host fica em `ambiente_coletado.txt`, regravada por `scripts/00_verificar_host.sh`; o snapshot de cada coleta fica no `.meta.json` da rodada.

## Hardware

| Item | Valor |
| --- | --- |
| Equipamento | Lenovo ThinkPad E14 Gen 3 |
| CPU | AMD Ryzen 5 5500U (6 núcleos, 12 threads) |
| Memória | 8 GB instalados; 6,6 GiB visíveis ao sistema |
| Disco | SSD NVMe 256 GB (SSSTC CL1-4D256) |

## Software do host

| Item | Valor |
| --- | --- |
| Sistema operacional | Bluefin 44.20261022.1 (base Fedora 44) |
| Kernel | 7.2.7-200.fc44.x86_64 |
| Docker | 29.9.2 (runtime `runc`) |
| Python (host) | 3.14.8 |
| Commit do SeBS | `b37f475542436ffb6b0ad03bd5972a680ecb8186` |
| `strace` e `perf` | não instalados (`perf_event_paranoid` = 2) |
| Atualizações automáticas | ativas durante o piloto; desativar na coleta principal e registrar as versões por rodada |

## Docker e cgroups

| Item | Valor |
| --- | --- |
| Driver de armazenamento | `overlayfs` |
| Sistema de arquivos do Docker | `btrfs` em `/dev/nvme0n1p3[/var]` (`DockerRootDir` = `/var/lib/docker`) |
| cgroups | v2 (`cgroup2fs`), driver `systemd` |
| Limite de CPU dos contêineres | `--cpus 1` (cota de 1 CPU de tempo, não afinidade a um núcleo), constante em todas as configurações; valor efetivo na coluna `nano_cpus` do CSV |
| Swap dos contêineres | `--memory-swap` igual a `--memory` (sem swap), constante |

## CPU e swap do host

| Item | Valor |
| --- | --- |
| Governador | `performance` (driver `amd-pstate-epp`) |
| Swap do host | `/dev/zram0` presente (6,6 GiB); `swapoff -a` não a remove de forma persistente |
| Política de swap | Uso de swap deve ser 0 kB durante a coleta; o orquestrador mede e interrompe se houver uso (`swap_max_kb = 0` em `configs/criterios.json`) |

## Imagens (reconferir com `docker images --digests`)

Construídas por `scripts/construir_imagens.sh`.

| Imagem | ID |
| --- | --- |
| `spcleth/serverless-benchmarks:run.local.python.3.11` (Python 3.11.17) | `3224d477dc17` |
| `spcleth/serverless-benchmarks:run.local.nodejs.20` (Node.js v20.20.2) | `a12b108a27b6` |
| `cs-sebs-node-base:orig` (imagem original do SeBS usada como base do patch do Node) | `0f480bed27b3` |
| `scylladb/scylla:6.2` | `a9d904089abe` |
| `cs-minio:fixed` (imagem Chainguard congelada, pois a oficial saiu do Docker Hub) | `709099319add` |

A imagem do Node é derivada de `cs-sebs-node-base:orig` com o patch `configs/patches/nodejs-path.Dockerfile`.

## Condições de cada rodada

| Item | Rodada 1 | Rodada 2 | Rodada 3 |
| --- | --- | --- | --- |
| Data e hora | | | |
| Na tomada (sim ou não) | | | |
| Temperatura média da CPU | | | |
| Frequência da CPU | | | |
| Uso de swap | | | |
| Versão do kernel e do Docker | | | |