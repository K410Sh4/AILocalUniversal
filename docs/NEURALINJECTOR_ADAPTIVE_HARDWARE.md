# Adaptive Hardware — estado e contrato de execução

Complemento da NIP 0.1.0. Consulte a [especificação](NEURALINJECTOR_NIP_0.1.0.md), os [perfis JSON](../examples/neuralinjector/hardware/profiles/) e o [planejador](../core/neuralinjector/resources.py).

## O que o código oferece agora

O módulo `core/neuralinjector/resources.py` contém planejamento backend-agnóstico e políticas de recursos:

- Detecção de RAM total/disponível e contagem de CPU pela biblioteca padrão.
- Inventário de GPU opcional: `nvidia-smi` para NVIDIA e sysfs DRM no Linux para dispositivos PCI visíveis, incluindo VRAM dedicada AMD quando os contadores existem.
- Distinção entre GPU detectada e backend de execução registrado. Detectar uma placa não prova que CUDA, ROCm ou Vulkan esteja inicializado.
- Orçamento conservador por dispositivo: VRAM de placas distintas não é somada como se fosse memória unificada.
- Seleção entre cinco perfis: `ultra_light`, `minimal`, `balanced`, `performance` e `max_quality`.
- Requisitos de RAM, VRAM, disco, contexto, backend e features.
- Relatórios de compatibilidade, perfis elegíveis, fallbacks e modo de proteção.
- Candidatos de quantização condicionados à lista de formatos que o backend declarar suportar.
- Avaliador de pressão de memória com histerese, para orientar limites de novas cargas, concorrência e sessões futuras.

A detecção de GPU é opt-in. A medição de espaço livre em disco exige que o chamador informe o diretório de destino. Sem medição confiável, um requisito obrigatório não é presumido como atendido.

## Perfis canônicos iniciais

| Perfil | RAM mínima | Fração máxima da RAM disponível | Contexto-alvo | Paralelismo |
|---|---:|---:|---:|---:|
| `ultra_light` | 1.536 MiB | 35% | 1.024 | 1 |
| `minimal` | 2.048 MiB | 55% | 2.048 | 1 |
| `balanced` | 4.096 MiB | 65% | 4.096 | 1 |
| `performance` | 8.192 MiB | 75% | 8.192 | 2 |
| `max_quality` | 16.384 MiB | 80% | 16.384 | 4 |

Os mínimos de RAM são critérios iniciais do perfil, não promessas de que determinado modelo caiba no orçamento. O tamanho dos pesos, KV cache, batch, runtime, multimodalidade e processos do sistema podem exigir muito mais memória. Um perfil de 1,5 GiB não torna viável um modelo de 7B ou maior.

## Quantização: política, não conversão

Cada perfil ordena candidatos de quantização por condição de memória. O planejador só retorna um candidato quando recebe uma lista explícita de quantizações aceitas pelo backend.

- Sem a lista de capacidades, nenhum formato é escolhido.
- Sem candidato em comum, o relatório registra a incompatibilidade.
- A política não converte pesos, não baixa outra variante e não altera um modelo já instalado.
- O runtime futuro deverá resolver o artefato real, verificar arquitetura/digest e somente então pedir sua carga ao backend.

## Modos de proteção

- `permissive`: permite uma tentativa explícita mesmo com incompatibilidades; o relatório preserva todos os motivos. Não é o padrão recomendado.
- `adaptive`: tenta selecionar um perfil elegível inferior. Requisitos mínimos declarados pelo pacote continuam obrigatórios.
- `protected`: além dos requisitos mínimos, recusa um perfil explicitamente solicitado quando ele não é elegível.

O planejador fornece `activation_allowed`, mas o carregador/gerenciador precisa respeitar esse valor antes de ativar um pacote. A NIP ainda não tem um NeuralPlugin Manager completo; portanto, o bloqueio de instalação/ativação ainda não está ligado a um fluxo real de instalação.

## Pressão dinâmica e histerese

`AdaptiveResourceManager.evaluate(snapshot)` recalcula a política quando recebe um novo snapshot. Os estados são:

- `normal`: nenhuma redução sugerida.
- `constrained`: evitar cargas pesadas e reduzir concorrência de novas solicitações quando necessário.
- `critical`: pausar novas cargas e recomendar contexto/concorrência menores.
- `emergency`: recusar novas cargas e suspender trabalho opcional ainda não iniciado.

A recuperação usa histerese: a memória precisa ultrapassar um limite de recuperação antes de abandonar um estado de pressão. Isso reduz oscilações rápidas. A classe `ResourceMonitor` pode fazer amostragem periódica (padrão de 5 segundos), mas só começa após `start()`; por padrão lê RAM/CPU e pode receber um provedor de snapshot e callback próprios. O callback roda na thread do monitor e deve encaminhar atualizações de UI para a thread principal. O avaliador/monitor retorna ações sugeridas; não encerra gerações em curso, não descarrega modelos nem controla filas por conta própria. Ainda falta ligar o monitor ao ciclo de vida da aplicação e implementar um executor de ações seguro.

## Integração inicial com Ollama

O adaptador `engines/ollama_engine.py` agora oferece:

- `list_running_models()`, que consulta `GET /api/ps` e normaliza nome, tamanho residente, `size_vram`, contexto e nível de quantização quando informados pelo servidor.
- `apply_resource_budget(request, budget)`, que aplica `num_ctx` ao objeto de opções da solicitação e nunca aumenta um limite de contexto menor definido pelo usuário.

A API do Ollama documenta `/api/ps` para listar modelos carregados e informa o uso de VRAM em `size_vram`; também aceita parâmetros do modelo em `options`, incluindo `num_ctx`. Referências: [API /api/ps](https://github.com/ollama/ollama/blob/main/docs/api.md#list-running-models), [opções de contexto](https://github.com/ollama/ollama/blob/main/docs/faq.mdx#how-can-i-specify-the-context-window-size).

**Limites desta integração:** a aplicação ainda não chama automaticamente esses métodos no fluxo principal de chat. O helper de orçamento precisa ser chamado pelo consumidor antes de enviar a solicitação. O código não configura paralelismo global do servidor, não força GPU/CPU, não faz offloading manual, não descarrega modelos e não converte quantização. O Ollama continua responsável pela distribuição de camadas e pela execução que realmente suporta.

## Limitações conhecidas

- A enumeração cobre NVIDIA via `nvidia-smi` e dispositivos Linux DRM; ainda não há detector dedicado para Windows/macOS, ROCm API ou Vulkan.
- iGPUs que não expõem memória dedicada são identificadas como memória compartilhada/desconhecida; não recebem uma VRAM fictícia.
- A seleção de GPU do Ollama não é derivada apenas da presença física de uma placa. Um backend executável precisa ser registrado e a telemetria real deve ser consultada.
- O orçamento de RAM é um teto planejado, não uma reserva do sistema operacional.
- Quantização, offloading, poda e transformações de pesos não são executados pelo planejador.
- O benchmark padrão permanece `none`; quick/full exigem solicitação e executor explícitos.
- Os testes unitários foram adicionados, mas precisam ser executados no ambiente de desenvolvimento/CI antes de considerar esta entrega validada.

## Próximas integrações

1. Ligar detecção e planejamento ao ciclo de solicitação do AILocal Universal.
2. Adicionar monitor periódico em worker, com cancelamento e limites de overhead.
3. Ligar o avaliador de pressão a uma política de novas cargas e componentes opcionais.
4. Integrar medição real e opções aceitas do Ollama; depois adicionar llama.cpp.
5. Validar em máquinas de 4–8 GiB, 16 GiB e 32+ GiB, incluindo GPU dedicada e iGPU.
