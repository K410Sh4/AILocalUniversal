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
| Núcleo cognitivo | Input Processing, Semantic Analysis, ferramentas determinísticas e Cognitive Planner integrados ao envio do Chat |
| Ferramentas locais | Calculadora AST restrita e conversões de comprimento, massa, tempo, dados e temperatura |
| Testes | Testes unitários para protocolo simulado, seleção, persistência, análise, ferramentas e rotas cognitivas |
| RAG | Planejado para Fase 3 |
| Resource Manager | Planejado para Fase 4 |
| Swarm P2P | Planejado para Fase 5 |
| BitNet e RPC | Laboratório futuro |

## Limitações conhecidas

- A afinidade de capacidades é lexical e heurística; não usa embeddings, não é calibrada e ainda não seleciona modelos especialistas por domínio.
- O histórico local usa JSON; banco de dados e migrações serão avaliados conforme escala.
- O adaptador Ollama foi implementado com transporte HTTP simulado nos testes, mas precisa de teste de integração com Ollama real.
- A interface foi construída, mas precisa ser validada em sessão gráfica Linux/Qt.
- As ferramentas determinísticas cobrem apenas operações e unidades explicitamente suportadas; solicitações fora desse conjunto seguem para o Ollama.
- O pipeline cognitivo inicial executa localmente e de forma síncrona no fluxo de envio da interface; estágios pesados ou externos devem ser movidos para workers antes de ampliar o pipeline.
