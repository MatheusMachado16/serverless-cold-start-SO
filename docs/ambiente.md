# Registro do ambiente

Preencher antes da coleta definitiva.

| Item | Valor |
| --- | --- |
| Equipamento | Lenovo ThinkPad E14 Gen 3 |
| CPU | AMD Ryzen 5 5500U (6 núcleos, 12 threads) |
| Memória | 8 GB |
| Disco | SSD NVMe 256 GB (SSSTC CL1-4D256) |
| Sistema operacional | Ubuntu 24.04.5 LTS |
| Kernel | 7.0.0-34-generic |
| Docker | 29.8.1 (build 4a63305) |
| Python | 3.12.3 |
| Commit do SeBS | b37f475542436ffb6b0ad03bd5972a680ecb8186 |
| Governador da CPU (valor real durante a coleta) | (padrão do sistema: powersave; preencher após ajustar) |
| Driver de frequência | (resultado do scaling_driver) |
| Driver de armazenamento do Docker | (preencher: `docker info \| grep -i "storage driver"`) |
| Sistema de arquivos do Docker | (preencher: `findmnt -no FSTYPE,SOURCE /var/lib/docker`) |
| Versão de cgroups | (preencher: `stat -fc %T /sys/fs/cgroup`; `cgroup2fs` = v2) |
| Política de swap do host | (preencher: `swapon --show`) |
| Limite de CPU e swap dos contêineres | (definir no piloto e manter constante) |
| Imagens e identificadores | (preencher após o build: `docker images --digests`) |
| Versões de Python e Node.js nas imagens | (preencher após o build) |
| `strace` e `perf` | (preencher: `strace -V`, `perf --version`) |

## Condições de cada rodada

| Item | Rodada 1 | Rodada 2 | Rodada 3 |
| --- | --- | --- | --- |
| Data e hora | | | |
| Na tomada (sim ou não) | | | |
| Temperatura média da CPU | | | |
| Frequência da CPU | | | |
| Uso de swap | | | |