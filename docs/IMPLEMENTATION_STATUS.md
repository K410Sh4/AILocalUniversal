# Estado da implementação

Este arquivo diferencia código existente de funcionalidades futuras.

| Área | Estado |
|---|---|
| README e documentação de arquitetura | Atualizados para a Fase 1 e a implementação inicial da Fase 2 |
| Interface PySide6 | Chat, inventário de modelos, preferências e configurações implementados |
| CognitiveTask | Contrato e serialização inicial implementados |
| ExecutionTrace | Registro local básico implementado |
| Orchestrator | Pipeline sequencial assíncrono com trace por estágio; usado no pipeline cognitivo |
| Capability Vectorizer | Vetor lexical heurístico de 12 dimensões; embeddings e calibração pendentes |
| Engine Adapter | Contrato e registry implementados |
| Ollama | Health check, listagem de modelos, chat NDJSON streaming e tratamento de erros implementados |
| Seleção de modelos | Manual e automático determinístico implementados |
| Histórico | Persistência JSON local, escrita atômica e permissões privadas implementados |
| Configurações | Persistência JSON local e validação básica implementadas |
| Workers | Operações HTTP fora da thread da interface e cancelamento cooperativo implementados |
| Núcleo cognitivo | Input Processing, Semantic Analysis, Task Decomposer, ferramentas determinísticas e Cognitive Planner integrados ao envio do Chat |
| Cognitive Inspector | Painel somente de leitura da última tarefa da sessão, incluindo análise, plano, subtarefas, modelo, resultado e trace de geração |
| Ferramentas locais | Calculadora AST restrita e conversões de comprimento, massa, tempo, dados e temperatura |
| Testes | Testes unitários para protocolo simulado, seleção, persistência, análise, ferramentas e rotas cognitivas |
| RAG | Planejado para Fase 3 |
| Resource Manager | Planejado para Fase 4 |
| Swarm P2P | Planejado para Fase 5 |
| BitNet e RPC | Laboratório futuro |

## Limitações conhecidas

- A afinidade de capacidades é lexical e heurística; não usa embeddings e não é calibrada. Modelos especialistas por domínio ainda não são selecionados automaticamente.
- A decomposição identifica listas e conectores explícitos, mas não cria agentes, não executa subtarefas em paralelo e não faz merge independente de resultados.
- O histórico local usa JSON; banco de dados e migrações serão avaliados conforme escala.
- O adaptador Ollama foi implementado com transporte HTTP simulado nos testes, mas precisa de teste de integração com Ollama real.
- A interface foi construída, mas precisa ser validada em sessão gráfica Linux/Qt.
- As ferramentas determinísticas cobrem apenas operações e unidades explicitamente suportadas; solicitações fora desse conjunto seguem para o Ollama.
- O pipeline cognitivo inicial executa localmente e de forma síncrona no fluxo de envio da interface; estágios pesados ou externos devem ser movidos para workers antes de ampliar o pipeline.
- O Cognitive Inspector mantém apenas a última tarefa em memória durante a sessão; não existe persistência nem consulta de tarefas antigas.
- O renderizador matemático implementa um subconjunto local de LaTeX; comandos e ambientes não suportados permanecem visíveis e não são adivinhados. Fórmulas em `\\[...\\]` e `$...$` usam blocos centralizados destacados.
- Equações display usam fonte absoluta de `20pt`: o rich text do Qt documenta `pt` e `px` para `font-size`; `em` não consta entre as unidades CSS suportadas.
