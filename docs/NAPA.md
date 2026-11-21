# Neural Adaptive Plasticity Architecture (NAPA)

## Objetivo

NAPA é a camada de coordenação cognitiva adaptativa do AILocal Universal. Sua responsabilidade é identificar capacidades necessárias, representar áreas cognitivas e, nas etapas futuras, selecionar caminhos de execução e aprender quais rotas operacionais são úteis.

NAPA é uma arquitetura acima dos componentes de execução, não um substituto do Cognitive Core, NeuralModel Hub, NeuralMap, Knowledge/RAG, Adaptive Resource Manager ou Neural Elastic Execution.

## NAPA 1.0 — Cognitive Area Registry & Classifier

Esta entrega inicial implementa:

- registro declarativo e extensível de áreas cognitivas;
- três tipos de componente: ferramenta determinística, capacidade cognitiva e especialista neural;
- classificação multilabel de uma mesma solicitação;
- reuso do intent e do Capability Vectorizer existentes;
- explicações por sinais que ativaram cada área;
- integração com SemanticAnalysisStage e CognitiveTask;
- serialização retrocompatível de cognitive_areas.

O classificador não carrega modelos, não executa ferramentas, não seleciona runtimes e não altera pesos.

## Taxonomia padrão

| Área | Tipo inicial | Sinais principais |
|---|---|---|
| mathematics | deterministic_tool | math_logic, cálculo |
| conversion | deterministic_tool | unit_conversion |
| communication | cognitive_capability | linguagem, explicação e conversa |
| social_cordiality | cognitive_capability | tom, cordialidade e formalidade explicitamente solicitados |
| reasoning | cognitive_capability | planejamento, comparação, verificação e análise |
| opinion | cognitive_capability | avaliação e recomendação |
| creativity | cognitive_capability | ideação e criação |
| generation | cognitive_capability | produção de artefatos |
| programming | neural_specialist | programação e depuração |
| knowledge | cognitive_capability | conhecimento conceitual e científico |
| retrieval | deterministic_tool | memória e recuperação de documentos |
| perception | neural_specialist | imagem, áudio e vídeo |
| tool_use | deterministic_tool | operações locais controladas |

A taxonomia é inicial e extensível. Uma área descrita como neural_specialist não implica que exista um modelo específico instalado ou que a área será ativada em execução.

## Classificação e significado dos scores

Cada ativação contém:

- area_id e kind;
- affinity entre 0 e 1;
- signals, por exemplo capability:programming, intent:programming ou anchor:python.

Affinity é uma afinidade heurística explicável, não probabilidade calibrada, confiança factual nem garantia de qualidade. O método combina o maior score legado aplicável, a afinidade do intent e as âncoras lexicais encontradas. As ativações são ordenadas por afinidade decrescente e ID como desempate estável.

A classificação é multilabel: uma consulta pode ativar mathematics, programming, communication, generation e social_cordiality ao mesmo tempo. Não é uma decisão de roteamento exclusiva.

## Integração com o Cognitive Core

SemanticAnalysisStage continua responsável por classificar intent, produzir o vetor de capacidades e estimar dificuldade, incerteza, risco e urgência. Em seguida chama CognitiveAreaClassifier com os resultados já calculados, evitando um segundo vocabulário paralelo para as 12 dimensões existentes.

O resultado é armazenado em CognitiveTask.cognitive_areas. O campo é aditivo e opcional ao ler payloads antigos; sua ausência é interpretada como classificação NAPA ainda não executada, nunca como aprovação ou ausência definitiva de capacidades.

## Extensões

Uma extensão pode criar CognitiveArea e registrá-la em CognitiveAreaRegistry. Os contratos validam IDs, tipo, dimensões reconhecidas e limites de afinidade. Esta versão registra definições em memória; persistência, descoberta de plugins, permissões e carregamento de código externo não fazem parte da NAPA 1.0.

## Limites e segurança

- O classificador é lexical e heurístico; scores não são probabilidades calibradas.
- Uma área identificada não autoriza automaticamente uma ferramenta, rede, modelo ou plugin.
- Nenhuma saída de LLM torna-se verificada por ter sido classificada.
- A frequência de ativação não atualiza prioridades nem fortalece conexões nesta versão.
- Nenhum parâmetro de modelo é alterado.
- Não há roteamento adaptativo, estimativa de custo, busca progressiva ou reorganização plástica nesta etapa.
- A execução continua sob o Cognitive Planner, Validation Layer e políticas existentes.

## Próximas etapas

1. NAPA 1.1 — Neural Cognitive Cost Predictor, separando RAM, VRAM, CPU, GPU, I/O, latência e energia.
2. NAPA 1.2 — Adaptive Cognitive Routing, com orçamento, dependências, fallback e validação.
3. NAPA 1.3 — Neural Progressive Retrieval, expandindo índices e domínios quando a evidência for insuficiente.
4. NAPA 1.4 — Neural Plasticity Engine, atualizando prioridades apenas com resultados avaliados.
5. NAPA 1.5 — Adaptive Neural Reorganization, com versionamento, avaliação e rollback.
6. NAPA 1.6 — Continual Performance Learning, preservando tarefas raras e evitando regressões.

## Validação

Os testes cobrem unicidade do registro, validação de contratos, classificação multilabel, separação entre ferramentas e especialistas, sinais explicáveis, injeção de scores existentes, compatibilidade de payloads antigos e integração com SemanticAnalysisStage.

A NAPA 1.0 não demonstra, por si só, economia de RAM, VRAM, latência ou tokens/s. Essa hipótese será avaliada nas etapas de custo, roteamento e aprendizagem, comparando sistemas estático, seletivo, adaptativo e plástico com as mesmas tarefas.
