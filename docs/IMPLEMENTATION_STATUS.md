# Estado da implementação

Este arquivo diferencia código existente de funcionalidades futuras.

| Área | Estado |
|---|---|
| README e documentação de arquitetura | Inicializados e atualizados para a Fase 1 |
| Interface PySide6 | Chat, inventário de modelos, preferências e configurações implementados |
| CognitiveTask | Contrato e serialização inicial implementados |
| ExecutionTrace | Registro local básico implementado |
| Orchestrator | Pipeline sequencial assíncrono implementado |
| Capability Vectorizer | Taxonomia e validação do vetor; classificação semântica pendente |
| Engine Adapter | Contrato e registry implementados |
| Ollama | Health check, listagem de modelos, chat NDJSON streaming e tratamento de erros implementados |
| Seleção de modelos | Manual e automático determinístico implementados |
| Histórico | Persistência JSON local, escrita atômica e permissões privadas implementados |
| Configurações | Persistência JSON local e validação básica implementadas |
| Workers | Operações HTTP fora da thread da interface e cancelamento cooperativo implementados |
| Testes | Testes unitários para protocolo simulado, seleção e persistência adicionados |
| RAG | Planejado para Fase 3 |
| Resource Manager | Planejado para Fase 4; planejador inicial NeuralInjector implementado (RAM/CPU, perfis, orçamento e relatório; integração GPU/backend pendente) |
| Swarm P2P | Planejado para Fase 5 |
| BitNet e RPC | Laboratório futuro |

## Limitações conhecidas

- O modo automático desta fase escolhe o modelo preferido se estiver disponível; caso contrário, escolhe o nome em ordem estável. Não faz classificação semântica.
- O histórico local usa JSON; banco de dados e migrações serão avaliados conforme escala.
- O adaptador Ollama foi implementado com transporte HTTP simulado nos testes, mas precisa de teste de integração com Ollama real.
- A interface foi construída, mas precisa ser validada em sessão gráfica Linux/Qt.
- Os testes foram escritos; a execução da suíte depende de ambiente com as dependências instaladas.
