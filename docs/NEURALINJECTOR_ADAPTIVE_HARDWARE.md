# Adaptive Hardware — fundação de recursos

Esta entrega integra a fundação independente de hardware do NeuralInjector. Ela fornece detecção, perfis canônicos, relatórios de compatibilidade e recomendações dinâmicas. **Ainda não controla quotas físicas, não altera o offload do Ollama e não está conectada ao fluxo de chat da interface.**

## Componentes disponíveis

- `core/neuralinjector/resources.py`: contratos de hardware, perfis, detecção de RAM/GPUs, orçamento e relatório de compatibilidade.
- `core/neuralinjector/monitor.py`: monitor opt-in com amostragem periódica e histerese.
- `examples/neuralinjector/hardware/profiles/`: serializações dos cinco perfis canônicos.
- `schemas/neuralinjector-hardware-profile.schema.json`: schema dos perfis exportados.
- `scripts/sync_neuralinjector_profiles.py`: regenera ou verifica os JSON canônicos.

## Perfis canônicos

| Perfil | RAM mínima total/disponível | Fração máxima de RAM disponível | Contexto mínimo/alvo | Threads CPU máx. | Concorrência-alvo |
|---|---:|---:|---:|---:|---:|
| `ultra_light` | 1.536 MiB | 35% | 512 / 1.024 | 2 | 1 |
| `minimal` | 2.048 MiB | 55% | 1.024 / 2.048 | 4 | 1 |
| `balanced` | 4.096 MiB | 65% | 2.048 / 4.096 | 8 | 1 |
| `performance` | 8.192 MiB | 75% | 4.096 / 8.192 | 16 | 2 |
| `max_quality` | 16.384 MiB | 80% | 8.192 / 16.384 | 16 | 4 |

O perfil automático escolhe o perfil de maior capacidade entre os elegíveis. A seleção considera RAM total e disponível; a detecção de GPU é opt-in e não registra automaticamente um backend de inferência.

## Semântica e segurança

- `ram_limit_mb` é um teto lógico recomendado, não uma quota do sistema operacional.
- `vram_limit_mb` representa a VRAM livre reportada para um único dispositivo; GPUs distintas não são somadas como memória unificada.
- `context_tokens` nunca deve exceder o alvo do perfil, mesmo quando o modo permissivo autoriza uma tentativa incompatível.
- `parallelism` é concorrência lógica; `cpu_threads` é o limite de threads sugerido ao backend.
- A quantização é apenas uma lista ordenada de candidatos. Escolher uma variante não converte os pesos.
- Um dispositivo GPU detectado não prova que CUDA, ROCm, Vulkan ou qualquer backend esteja inicializado.

O piso absoluto desta implementação é 1.536 MiB de RAM total e disponível. Abaixo dele, a ativação é bloqueada inclusive no modo permissivo.

## Monitor dinâmico

`ResourceMonitor` é inerte até `start()`. Ele coleta snapshots, calcula estados de pressão com histerese e publica recomendações. Não mata gerações, não descarrega modelos e não suspende processos. Callbacks do monitor periódico são executados na thread de monitoramento; uma interface gráfica deve encaminhar atualizações para a thread de UI.

Os estados são `normal`, `constrained`, `critical` e `emergency`. O monitor recomenda pausar novas cargas ou reduzir contexto/concorrência, mas a aplicação chamadora ainda precisa aplicar políticas compatíveis e seguras.

## Limitações atuais

1. O monitor não está conectado à interface principal nem ao Adaptive Model Selector.
2. Não existem quotas físicas de RAM/VRAM, cgroups, limites de GPU ou gerenciamento de offload.
3. A detecção de GPU é best-effort; memória desconhecida permanece desconhecida.
4. Benchmarks só são executados quando o chamador fornece explicitamente uma função de benchmark.
5. Os coeficientes e perfis são políticas iniciais; ganhos de desempenho precisam ser medidos em hardware real.
6. A ponte de orçamento para Ollama e a criação de runtime llama.cpp ainda exigem integração e validação operacional nesta branch.

## Validação

Os testes unitários cobrem seleção de perfis, requisitos mínimos, modos de proteção, candidatos de quantização, detecção de GPU sem presumir backend, histerese do monitor e sincronização entre os perfis Python e JSON.

Para regenerar os perfis após uma alteração:

```bash
python scripts/sync_neuralinjector_profiles.py
```

Para verificar sem modificar arquivos:

```bash
python scripts/sync_neuralinjector_profiles.py --check
```
