# Protocolo: decisões do piloto e critérios de validação

Cada item da seção 12 do README vira aqui uma decisão registrada. Enquanto o piloto não rodar, tudo está **pendente**. Quando decidirmos, escrever a decisão, a evidência e a data.

| # | O que precisa ser decidido | Como o piloto valida | Decisão |
| --- | --- | --- | --- |
| 1 | O ambiente local com Docker e a definição de cold start (`t0` até `t_resp`) são adequados | 5 cold starts por configuração; conferir se `T_cold_total` é estável e interpretável | pendente |
| 2 | A1 (`130.crud-api`) e A2 (`210.thumbnailer`) funcionam e são equivalentes em Python e Node.js | Mesma entrada nos dois runtimes; comparar a saída e o que é gravado no ScyllaDB e no Minio | pendente |
| 3 | Limites de memória de 128 e 256 MiB são viáveis | Verificar OOM com `docker inspect` e `memory.events` | pendente |
| 4 | Quais patches no SeBS são necessários (`mem_limit`, `network_mode`) | `docker inspect` do contêiner criado: conferir limite e rede reais. *Observação inicial no commit `b37f475`: `sebs/local/local.py` fixa `network_mode: "bridge"` e não define `mem_limit`; confirmar no piloto.* | pendente |
| 5 | Como são os pacotes mínimo, padrão e ampliado, e o que é só presente × realmente importado | Medir tamanho, número de arquivos e arquivos abertos (`strace`) em cada pacote | pendente |
| 6 | Prontidão sem executar a carga antes da requisição medida; instrumentação cobre o início do runtime | Sinal explícito do wrapper; checar nos rastros que o handler não rodou antes de `t_req` | pendente |
| 7 | Descarte combinado de caches (`drop_caches=3`) é aceito; interesse em análise com `=1` | Discutir com o professor | pendente |
| 8 | Quantidade de repetições, critérios ambientais que interrompem a coleta e tamanho do subconjunto instrumentado | Variabilidade (CV, IC) do piloto; limites de temperatura, swap e frequência | pendente |

## Critérios ambientais de interrupção (definir no piloto)

| Variável | Limite | Ferramenta |
| --- | --- | --- |
| Temperatura da CPU | a definir | `sensors` |
| Atividade de swap | a definir (ideal: nenhuma) | `vmstat` |
| RAM disponível | a definir | `free` |
| Notebook fora da tomada | interromper a coleta | — |
