# Adaptive Hardware — arquitetura, execução e limites

Complemento técnico da **NeuralInjector Package Specification (NIP) 0.1.0**. Esta página descreve o código que existe nesta branch, como os perfis são aplicados no chat com Ollama e quais etapas continuam pendentes.

Referências: [NIP 0.1.0](NEURALINJECTOR_NIP_0.1.0.md), [perfis JSON](../examples/neuralinjector/hardware/profiles/), [planejador Python](../core/neuralinjector/resources.py), [monitor](../core/neuralinjector/monitor.py), [ponte Ollama](../engines/ollama_engine.py), [ponte llama.cpp](../engines/llama_cpp_options.py).

## 1. Modelo de execução

O Adaptive Hardware separa cinco responsabilidades:

1. **Detecção:** coleta RAM total/disponível, CPU e, quando solicitado, inventário de GPU/VRAM.
2. **Planejamento:** seleciona um perfil elegível e calcula orçamento de RAM, VRAM, contexto, concorrência e threads de CPU.
3. **Proteção:** avalia requisitos do pacote e decide se a solicitação pode prosseguir.
4. **Tradução para backend:** transforma apenas os campos que o backend realmente aceita em opções executáveis.
5. **Telemetria:** consulta uso reportado pelo backend e pode recalcular recomendações a partir de novos snapshots.

Fluxo implementado na solicitação de chat:

```text
Usuário envia mensagem
        |
        v
Detectar RAM e núcleos de CPU
        |
        v
Selecionar perfil e gerar CompatibilityReport
        |
        +---- incompatível / protected ----> mostrar motivo e alternativas
        |
        v
Traduzir orçamento para opções Ollama
        |
        v
Adicionar mensagem ao histórico
        |
        v
Enviar /api/chat
```

A pré-validação acontece **antes** de gravar a mensagem no histórico e antes de fazer requisição ao Ollama. A recusa não cria uma resposta vazia nem envia o prompt ao backend.

## 2. Fonte canônica dos perfis

A definição normativa dos perfis fica em `CANONICAL_PROFILES` no arquivo `core/neuralinjector/resources.py`. Cada `HardwareProfile` fornece `to_dict()`, e `serialize_hardware_profile()` expõe a serialização pública.

Os JSON em `examples/neuralinjector/hardware/profiles/` são artefatos gerados a partir dessa definição. O teste de unidade compara cada arquivo com o dicionário produzido pelo perfil Python; divergências estruturais ou numéricas quebram o teste.

Para regenerar os exemplos após alterar um perfil:

```bash
python scripts/sync_neuralinjector_profiles.py
```

Para somente verificar se estão sincronizados:

```bash
python scripts/sync_neuralinjector_profiles.py --check
```

O JSON Schema `schemas/neuralinjector-hardware-profile.schema.json` valida o contrato serializado. Alterações em campos, tipos ou identificadores devem atualizar conjuntamente a classe Python, o schema, os exemplos e os testes.

## 3. Perfis canônicos

Os valores abaixo são limites de planejamento, não garantia de que qualquer modelo caiba no computador.

| Perfil | RAM total mínima | RAM disponível mínima | Fração da RAM disponível | Contexto mínimo | Contexto-alvo | Máx. threads CPU | Concorrência-alvo |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ultra_light` | 1.536 MiB | 1.536 MiB | 35% | 512 | 1.024 | 2 | 1 |
| `minimal` | 2.048 MiB | 2.048 MiB | 55% | 1.024 | 2.048 | 4 | 1 |
| `balanced` | 4.096 MiB | 4.096 MiB | 65% | 2.048 | 4.096 | 8 | 1 |
| `performance` | 8.192 MiB | 8.192 MiB | 75% | 4.096 | 8.192 | 16 | 2 |
| `max_quality` | 16.384 MiB | 16.384 MiB | 80% | 8.192 | 16.384 | 16 | 4 |

O perfil automático seleciona o perfil de maior capacidade entre os elegíveis. A escolha usa **RAM total e RAM disponível**: possuir 16 GiB instalados não torna o host elegível para um perfil de 16 GiB se a memória disponível naquele momento estiver abaixo do limite.

### 3.1 Semântica do orçamento

- `ram_limit_mb`: fração da RAM disponível que o planejador recomenda como teto de orçamento. Não cria uma reserva do kernel, cgroup ou sistema operacional.
- `vram_limit_mb`: VRAM livre medida para um dispositivo individual. Não é soma artificial de GPUs.
- `context_tokens`: contexto-alvo entregue ao adaptador, respeitando um limite menor já definido pelo usuário.
- `parallelism`: limite lógico de solicitações simultâneas pretendido pelo planejador. Não é número de threads.
- `cpu_threads`: limite de threads de CPU a traduzir para o backend.

Separar concorrência de threads evita o erro de interpretar `parallelism=1` como “usar somente uma thread de CPU”. O adaptador limita threads pela quantidade de núcleos detectados e pelo teto do perfil.

### 3.2 O que o perfil não promete

Um perfil `ultra_light` com orçamento de 1,5 GiB não torna viável um modelo de 7B, 14B ou maior. A memória real também depende de pesos, KV cache, tamanho do contexto, lote, arquitetura, runtime, multimodalidade, offloading e processos do sistema. A elegibilidade do perfil é somente uma primeira barreira; requisitos específicos do pacote/modelo precisam ser avaliados separadamente.

## 4. Piso absoluto de segurança

O planejador define **1.536 MiB de RAM total e disponível** como piso absoluto de elegibilidade desta implementação.

Abaixo desse valor:

- Nenhum perfil é considerado compatível.
- O modo protegido e o adaptativo recusam a carga.
- O modo permissivo também não consegue ultrapassar esse piso.
- O relatório contém uma explicação específica, em vez de apenas “hardware incompatível”.

A interface mostra uma janela de proteção com os motivos e alternativas. A mensagem deixa claro que nenhuma mensagem foi enviada ao Ollama. As ações sugeridas são fechar aplicativos pesados, descarregar modelos residentes, medir novamente e considerar um modelo menor ou mais RAM física.

Swap pode ajudar o sistema a sobreviver a pressão de memória em certos cenários, mas não é contabilizada como RAM disponível nem torna um modelo adequado para inferência. Pressão de swap pode aumentar muito a latência e não deve ser apresentada como solução garantida.

## 5. Modos de proteção e UX

A configuração persistente inclui:

- `hardware_profile`: `auto`, `ultra_light`, `minimal`, `balanced`, `performance` ou `max_quality`.
- `protection_mode`: `protected`, `adaptive` ou `permissive`.

Os valores padrão para instalações novas e configurações antigas migradas são `auto` e `protected`.

| Modo | Comportamento |
|---|---|
| `protected` | Recusa quando o perfil explicitamente escolhido não cabe ou quando requisitos obrigatórios não são cumpridos. |
| `adaptive` | Se um perfil preferido não cabe, tenta um perfil inferior elegível; requisitos mínimos continuam obrigatórios. |
| `permissive` | Permite tentativa explícita apesar de incompatibilidades não absolutas. Nunca ignora o piso de 1,5 GiB. |

Quando há recusa, `CompatibilityReport` fornece:

- `reasons`: motivos técnicos identificados.
- `fallbacks`: alternativas/recomendações geradas pelo planejador.
- `user_message`: explicação principal em linguagem direta.
- `recommendations`: próximos passos voltados ao usuário.
- `activation_allowed`: decisão que o chamador deve respeitar.

A janela do AILocal Universal mostra a explicação principal e um painel de detalhes com motivos e alternativas. O modo protegido não deve ser reduzido a uma caixa de erro genérica. A próxima evolução de UX poderá acrescentar ações diretas para abrir configurações e escolher o perfil automático/adaptativo; nesta versão, as opções ficam disponíveis no diálogo Configurações.

## 6. Integração aplicada com Ollama

O adaptador `engines/ollama_engine.py` possui `prepare_resource_aware_request()`, que executa planejamento e tradução antes da chamada de rede. Se o relatório não autorizar a solicitação, lança `OllamaResourceProtectionError` contendo o próprio `CompatibilityReport`.

### 6.1 Opções aplicadas por requisição

O orçamento é traduzido para:

| Campo Ollama | Origem | Efeito |
|---|---|---|
| `options.num_ctx` | `ResourceBudget.context_tokens` | Define o limite de contexto da requisição. |
| `options.num_thread` | `ResourceBudget.cpu_threads` | Limita threads de CPU usadas pelo runner. |

Um limite menor que o usuário já tenha definido é preservado. O adaptador não aumenta um `num_ctx` ou `num_thread` já configurado para um valor maior que o orçamento.

A documentação e os tipos da API do Ollama definem `num_ctx` e `num_thread` entre as opções do runner. A aplicação não depende de alterar o Modelfile para esses dois parâmetros por requisição.

### 6.2 Operações que continuam sob controle do Ollama

- **Posicionamento CPU/GPU:** o AILocal Universal não força GPU nem CPU com base apenas na detecção física. O Ollama faz o offload de acordo com o backend e os dispositivos efetivamente disponíveis.
- **Concorrência global:** `parallelism` é um limite de política do AILocal. Não altera por si só as variáveis/configurações globais do servidor Ollama.
- **Offloading:** o adaptador não move camadas manualmente.
- **Descarregamento:** consultar modelos carregados não significa que o adaptador os descarregue automaticamente.

### 6.3 Telemetria de modelos carregados

`list_running_models()` consulta `GET /api/ps` e normaliza o nome, tamanho residente, VRAM reportada, contexto e quantização quando disponíveis. Esses valores podem apoiar uma política futura de reavaliação. A telemetria do Ollama é a fonte para o que o próprio servidor informa; não deve ser confundida com detecção universal de VRAM de todo o computador.

### 6.4 Quantização no Ollama

Quantização não é uma opção que se altere na chamada `/api/chat`. Ela pertence ao artefato/modelo instalado (por exemplo, uma tag quantizada diferente). O AILocal Universal pode recomendar uma variante e ler a quantização reportada pelo modelo carregado, mas ainda não baixa, converte ou substitui automaticamente o modelo. Qualquer troca futura deve validar a identidade/arquitetura do modelo, disponibilidade do artefato, espaço em disco, licença e consentimento do usuário.

## 7. Ponte de opções para llama.cpp

O repositório inclui `engines/llama_cpp_options.py`, que traduz um `ResourceBudget` para argumentos do construtor `llama_cpp.Llama`:

| Orçamento AILocal | Argumento llama-cpp-python |
|---|---|
| `context_tokens` | `n_ctx` |
| `cpu_threads` | `n_threads` |
| camada GPU já validada pelo backend | `n_gpu_layers` (opcional) |

A camada de GPU é omitida por padrão; só é incluída se o chamador fornecer explicitamente uma contagem validada. O helper não presume que uma GPU detectada seja utilizável.

**Limite atual:** esta é a tradução testável de opções do construtor, não um `EngineAdapter` llama.cpp completo e ainda não está conectada ao seletor de backend da interface. As opções de contexto e threads do llama.cpp são aplicadas ao construir/recriar a instância do modelo; não são parâmetros de amostragem de cada token.

A quantização é incorporada ao arquivo GGUF selecionado. `n_ctx`, `n_threads` ou `n_gpu_layers` não convertem um arquivo FP16 em Q4 nem trocam uma variante Q4 por Q8.

## 8. Detecção de GPU e cautelas

O detector opcional fornece inventário de dispositivos via:

- `nvidia-smi` para NVIDIA.
- Linux DRM/sysfs para dispositivos PCI AMD, NVIDIA e Intel visíveis ao sistema.

A disponibilidade de VRAM dedicada é preenchida somente quando o driver expõe contadores confiáveis. iGPU com memória compartilhada não recebe um número fictício de VRAM dedicada. A maior VRAM disponível de um único dispositivo é usada no resumo; placas independentes não são somadas.

O inventário de GPU e o conjunto `execution_backends` são campos separados. Uma Radeon visível no sysfs não comprova que ROCm, Vulkan ou outro backend esteja inicializado. A aplicação desktop ainda usa detecção RAM/CPU no preflight de chat; o Ollama mantém sua própria seleção de dispositivo. A detecção GPU ainda não é usada para forçar a colocação de camadas.

## 9. Monitoramento durante a execução

`AdaptiveResourceManager.evaluate(snapshot)` classifica pressão de memória em quatro estados:

- `normal`: nenhuma redução dinâmica sugerida.
- `constrained`: evitar novas cargas pesadas e reduzir concorrência de solicitações futuras.
- `critical`: pausar novas cargas e recomendar redução do contexto de sessões futuras.
- `emergency`: recusar novas cargas e suspender tarefas opcionais ainda não iniciadas.

A histerese evita alternar de estado por pequenas oscilações. `ResourceMonitor` oferece amostragem periódica opt-in, com intervalo mínimo de um segundo e padrão de cinco segundos. É necessário chamar `start()`; o monitor não começa sozinho.

O monitor chama o provedor de snapshot e o callback na sua própria thread. Qualquer callback que altere interface deve encaminhar o trabalho para a thread Qt principal. O monitor não descarrega modelos, não mata gerações em andamento, não altera filas e não executa ações recomendadas. A integração desse monitor ao ciclo de vida do aplicativo e um executor seguro continuam pendentes.

## 10. Validação e testes

A suíte cobre contratos de recursos, perfis, modo protegido, piso absoluto, quantização declarativa, histerese, monitor, telemetria Ollama, aplicação de `num_ctx`/`num_thread` ao payload e tradução de opções llama.cpp.

Com ambiente de desenvolvimento instalado:

```bash
python scripts/sync_neuralinjector_profiles.py --check
python -m ruff check .
python -m pytest -q
```

Testes com transporte HTTP simulado demonstram que as opções chegam ao payload da chamada Ollama. Eles não substituem teste de integração com serviço Ollama real, nem benchmark em hardware físico.

## 11. Limitações conhecidas e trabalho restante

1. Criar um `EngineAdapter` llama.cpp completo e integrá-lo ao registro/seletor de modelos.
2. Consultar periodicamente telemetria de backend e integrar o ResourceMonitor ao ciclo de vida Qt, com baixo overhead.
3. Implementar executor seguro para pausar novas cargas, limitar fila e descarregar componentes opcionais somente quando o backend confirmar suporte.
4. Ligar a resolução de variantes quantizadas à disponibilidade de artefatos GGUF/Ollama, sem prometer conversão automática.
5. Adicionar detecção GPU robusta para mais plataformas e integrar métricas do backend efetivamente inicializado.
6. Validar em hosts abaixo de 4 GiB, máquinas intermediárias e workstations, registrando RAM/VRAM, modelo, quantização, contexto, versão do backend, latência e qualidade.

O objetivo é que o computador leve receba limites e recusas seguras quando não houver recursos, enquanto computadores potentes possam usar contextos e threads maiores com confirmação do backend. Não há promessa de velocidade absoluta independente do hardware.
