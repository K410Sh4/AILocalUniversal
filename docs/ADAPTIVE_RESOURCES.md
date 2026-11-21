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

A integração atual consulta `/api/tags` e `/api/show`, mas ainda não consulta `/api/ps`. O endpoint de modelos em execução fornece identidade/digest, tamanho reportado, uso de VRAM, contexto e expiração da residência. Esses dados permitem construir um provider de residência, mas não devem ser tratados como medição completa de RAM/KV sem validação no backend e no hardware.

**Correção arquitetural proposta para a próxima etapa:**

1. Adicionar um contrato `RunningModelSnapshot` ao Engine Adapter, com nome, digest, tamanho reportado, VRAM reportada, contexto e expiração quando disponíveis.
2. Consultar `/api/ps` no adaptador Ollama e reconciliar a identidade pelo digest do artefato, não apenas pelo nome/tag.
3. Separar custo de carregamento frio (pesos + KV + overhead) de custo incremental de uma instância já residente (KV/contexto adicional e buffers ainda não contabilizados).
4. Manter reservas de residência do modelo separadas dos leases temporários de cada tarefa. A reserva residente só é liberada após confirmação de unload/expiração; não liberar pesos ao terminar uma única geração se o runtime mantiver o modelo carregado.
5. Se a telemetria estiver indisponível, inconsistente ou com digest divergente, manter o caminho conservador de carregamento frio e registrar a incerteza.

O campo `context_length` reportado pelo runtime deve ser tratado inicialmente como metadado de configuração/execução, não como prova de ocupação exata do cache KV. O cálculo incremental precisa continuar conservador até ser comparado com RAM/VRAM observadas durante cargas frias e quentes.

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
