# Adaptive Resource Manager e Adaptive Model Selector

## Objetivo

A Fase 4.5 adiciona uma primeira camada de estimativa de memória e escolha explicável de modelos para o AILocal Universal. O serviço opera sobre o inventário e os metadados expostos pelo runtime; não altera ainda políticas internas do Ollama nem carrega/descarrega modelos automaticamente.

## Fluxo

1. O adaptador Ollama consulta `/api/tags` e `/api/show`.
2. Os metadados disponíveis são normalizados em `ModelInfo` e persistidos no `ModelRegistry`.
3. O `HardwareProfiler` coleta RAM disponível e VRAM disponível exposta pelo sysfs DRM.
4. O `ResourceEstimator` estima pesos, cache KV quando possível e reserva de runtime.
5. O `AdaptiveModelSelector` filtra modelos sem capacidade de chat verificada, estima candidatos e devolve uma decisão com justificativa e alternativas.
6. O modo Automático do Chat usa o seletor. O modo Manual permanece sob escolha explícita do usuário.

## Estimativa de pesos

A estimativa usa:

```text
peso_estimado = parâmetros_totais × bits_médios_por_parâmetro / 8 × fator_de_segurança
```

Coeficientes iniciais aproximados:

| Quantização | Bits médios usados |
|---|---:|
| Q4_K_M | 4,8 |
| Q4_K_S | 4,6 |
| Q4_0 | 4,5 |
| Q4_1 | 5,0 |
| Q5_K_M | 5,7 |
| Q5_K_S | 5,5 |
| Q5_0 | 5,5 |
| Q5_1 | 6,0 |
| Q6_K | 6,6 |
| Q8_0 | 8,5 |
| FP16 / BF16 | 16,0 |

O fator de segurança inicial é 1,12. Os coeficientes são aproximações de planejamento, não o tamanho exato dos pesos nem uma medida do processo de inferência. Quantizações desconhecidas não recebem um palpite.

Para modelos MoE, a estimativa dos pesos usa parâmetros totais, não parâmetros ativos por token. Ativação esparsa reduz operações por token, mas não significa que somente os especialistas ativos estejam armazenados no modelo.

O tamanho do arquivo baixado ou do artefato no disco não é usado como requisito de RAM/VRAM.

## Cache KV

O adaptador lê metadados explícitos de arquitetura no retorno de `/api/show`. Nesta iteração, calcula o cache KV FP16/token somente para arquiteturas densas suportadas e quando todos estes campos estão presentes:

- quantidade de blocos/camadas;
- quantidade de cabeças KV;
- dimensão de chave;
- dimensão de valor.

A fórmula aplicada é:

```text
KV_bytes_por_token = camadas × cabeças_KV × (dimensão_K + dimensão_V) × 2
```

O multiplicador 2 representa bytes por elemento FP16. A estimativa para um contexto é KV bytes/token × número de tokens.

Arquiteturas híbridas (por exemplo, combinações de atenção e mecanismos recorrentes) e arquiteturas desconhecidas não recebem uma estimativa de KV por esta fórmula. O sistema mantém a informação ausente como desconhecida. Uma estimativa parcial ainda pode detectar que o limite inferior de pesos + overhead excede toda a memória utilizável; nesse caso, o candidato é bloqueado.

## Margens de planejamento

- Reserva padrão de runtime: 768 MiB.
- Reserva de memória livre: 15% da RAM/VRAM atualmente disponível.
- O contexto usado pela integração inicial do Chat Automático é 4.096 tokens.

São parâmetros iniciais fixos desta versão. O overhead real varia por backend, arquitetura, contexto, cache, buffers, fragmentação, concorrência e implementação dos kernels; não é medido por essa reserva.

## Posicionamento sugerido

O estimador pode classificar:

- `gpu`: pesos + KV + reserva estimados cabem na VRAM disponível após margem.
- `cpu`: estimativa cabe na RAM disponível após margem.
- `hybrid`: a soma de RAM e VRAM disponíveis após margem comporta a estimativa; depende de suporte real a offload e não configura o offload.
- `does_not_fit`: a estimativa completa ou seu limite inferior conhecido excede a memória utilizável.
- `unknown`: faltam recursos ou metadados para concluir.

A identificação da GPU pelo sistema não prova que o backend do Ollama esteja usando-a. A confirmação operacional da distribuição deve ser feita com `ollama ps` e monitoramento do sistema.

## Política do seletor

1. Considera apenas modelos cujo runtime confirme capacidade de chat.
2. Mantém a preferência do usuário quando ela é estimada como viável.
3. Caso contrário, classifica os candidatos viáveis por categoria de tarefa (quando fornecida), posicionamento sugerido, menor memória estimada e nome estável.
4. Se só houver modelos com metadados insuficientes, mantém o fallback determinístico e explica que não verificou a memória.
5. Não seleciona um modelo cujo limite inferior conhecido já exceda os recursos medidos.
6. Se todos os modelos tiverem estimativa completa e não couberem, retorna erro explicável.

O seletor não altera o modo Manual e não define a qualidade real do modelo. A categoria de tarefa ainda não é inferida automaticamente pelo Cognitive Pipeline nesta entrega.

## Orçamento de processamento — perfis Leve, Médio e Ultra

A Fase 4.6 adiciona três perfis persistidos em `AppConfig.resource_profile` e disponíveis em Configurações:

| Perfil | Orçamento-alvo |
|---|---:|
| Leve (`light`) | 33% |
| Médio (`medium`) | 66% |
| Ultra (`ultra`) | 95% |

Na integração inicial com Ollama, o percentual é convertido em um limite aproximado de threads de CPU (`num_thread`), arredondado para o inteiro mais próximo e limitado à quantidade de núcleos lógicos detectada. Exemplo: em 12 threads lógicas, os limites calculados são 4, 8 e 11. A granularidade de threads faz com que o percentual resultante seja apenas uma aproximação.

**O que este controle realmente faz:** define o número de threads de CPU enviado ao Ollama para o runner. Não limita exatamente a porcentagem de CPU medida, não define afinidade de CPU e não impõe um limitador genérico de utilização de GPU. O Ollama não oferece, nesta integração, controle portátil de percentual de computação da GPU. O `num_thread` é uma opção do runner aplicada durante o carregamento do modelo; um modelo que já esteja carregado pode precisar ser descarregado/recarregado pelo runtime para refletir a alteração.

O perfil não é convertido em porcentagem de RAM/VRAM. A elegibilidade de modelos continua usando a estimativa separada de pesos, cache KV, RAM/VRAM disponível e margem de segurança. O seletor registra o perfil na explicação, mas não reduz artificialmente a memória disponível nem presume que 33% de CPU signifique 33% da memória. Como ainda não há benchmark de custo computacional por modelo, o seletor não afirma que um modelo consome exatamente a fração selecionada; a limitação concreta desta integração é o orçamento de threads. A filtragem de modelos por custo computacional específico do perfil permanece pendente até haver benchmarks por modelo, hardware e backend; por enquanto, o seletor não bloqueia um candidato apenas por previsão de lentidão.

A configuração antiga sem `resource_profile` é carregada como `medium`. O modo Manual continua respeitando o modelo selecionado pelo usuário; o orçamento de threads é aplicado às solicitações de inferência Ollama tanto no modo Manual quanto no Automático.

## Residência real de modelos — lacuna identificada na auditoria

O estimador atual calcula `pesos + cache KV + overhead` como requisito total e compara esse valor com a memória disponível observada pelo sistema. Isso é conservador para um carregamento frio, mas pode contar os pesos duas vezes quando o Ollama já mantém o modelo residente: a memória disponível do sistema já foi reduzida pela carga existente, enquanto a estimativa volta a incluir os pesos completos. Em máquinas com pouca RAM, isso pode rejeitar um modelo que já está carregado e cujo custo incremental seria principalmente o contexto/cache e buffers adicionais.

**Etapa 1 implementada na branch de integração:** o contrato `RunningModelSnapshot` foi adicionado ao Engine Adapter e `OllamaEngine.list_running_models()` consulta `GET /api/ps`. O snapshot normaliza nome, referência, digest, tamanho reportado, VRAM reportada, contexto, expiração e detalhes. Campos ausentes ou com tipos inválidos permanecem desconhecidos; entradas sem nome utilizável são ignoradas. Adaptadores sem telemetria mantêm compatibilidade pelo método padrão que retorna lista vazia.

**Limite deliberado:** `size` e `size_vram` são preservados como medidas reportadas separadas. Não são convertidos em RAM total, nem subtraídos automaticamente do estimador. A documentação do endpoint descreve modelos carregados e esses campos, mas não define uma decomposição completa da memória do processo em pesos, KV, buffers e overhead. O digest é a chave para futura reconciliação exata da versão do artefato; nomes/tags isolados não bastam.

**Etapa 2 implementada — reconciliação de identidade:** o módulo `resources.residency` compara o artefato instalado com o snapshot residente usando referência exata e digest. O `AdaptiveResourceManager.reconcile_residency()` expõe a consulta. Os estados são `confirmed`, `digest_missing`, `digest_mismatch`, `ambiguous`, `not_resident` e `artifact_missing`. Só a combinação única de referência instalada e digest coincidente recebe `confirmed`.

Esta etapa é deliberadamente informativa: mesmo quando a identidade é confirmada, o estimador e o seletor continuam usando o caminho conservador de memória fria. O endpoint não fornece decomposição suficiente para calcular com segurança o custo incremental de pesos, KV e buffers. Assim, nenhuma memória é subtraída e nenhum candidato passa a ser considerado viável apenas por estar residente.

**Próxima etapa — contabilização residente segura:**

1. Reconciliar o digest de `RunningModelSnapshot` com o digest do artefato instalado. Divergência ou digest ausente mantém o caminho frio/conservador.
2. Separar o custo de carregamento frio do custo incremental sem inferir uso de KV a partir apenas de `context_length`.
3. Não contar pesos novamente como nova alocação quando a identidade residente for comprovadamente idêntica e a medição de memória disponível já refletir a residência; preservar a margem para KV adicional, buffers e overhead ainda não medidos.
4. Manter reservas de residência separadas dos leases temporários por tarefa. A reserva só é liberada após confirmação de unload/expiração.
5. Validar as estimativas com medições simultâneas de RAM/VRAM e estados frios/quentes no Arch Linux.

O campo `context_length` reportado pelo runtime é a capacidade/configuração de contexto do runner, não prova da quantidade efetivamente ocupada no cache KV. O estimador incremental permanece pendente até haver uma política conservadora validada em cargas reais.

## Limites desta versão

Ainda não implementado:

- telemetria contínua de RAM/VRAM/CPU/GPU;
- aferição de memória do processo Ollama enquanto carrega e infere;
- benchmarks frios/quentes de latência, throughput, qualidade e estabilidade;
- contexto adaptativo configurável por tarefa;
- estimativa de cache quantizado;
- políticas de concorrência, leases e descarregamento;
- controle direto de camadas de GPU/offload;
- validação operacional em hardware real.

## Validação no ambiente-alvo

Para cada teste, registrar hardware, modelo/tag, quantização, contexto, estado frio/quente, RAM e VRAM antes/depois, distribuição exibida por `ollama ps`, tempo de carregamento e tokens/s.

Modelos MoE grandes devem ser avaliados pelo tamanho total dos pesos para estimativa de memória. Parâmetros ativos por token devem ser registrados como informação de computação, não usados como substituto do tamanho total dos pesos.
