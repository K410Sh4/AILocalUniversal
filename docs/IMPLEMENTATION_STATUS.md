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
| Ollama | Health check, inventário, chat NDJSON e tratamento de erros; preflight protegido aplica `num_ctx` e `num_thread` por requisição; `/api/ps` fornece telemetria de modelos carregados |
| Seleção de modelos | Manual e automático determinístico implementados |
| Histórico | Persistência JSON local, escrita atômica e permissões privadas implementados |
| Configurações | Persistência JSON local; perfil de hardware e modo de proteção configuráveis e validados |
| Workers | Operações HTTP fora da thread da interface e cancelamento cooperativo implementados |
| Testes | Testes unitários para protocolo simulado, seleção e persistência adicionados |
| RAG | Planejado para Fase 3 |
| Resource Manager | Planejador NeuralInjector integrado ao preflight de chat Ollama: RAM/CPU, cinco perfis sincronizados por serializador, piso absoluto, modos protected/adaptive/permissive, orçamento separado de threads/concorrência; detecção GPU e monitor opt-in disponíveis, executor dinâmico ainda pendente |
| Swarm P2P | Planejado para Fase 5 |
| BitNet e RPC | Laboratório futuro |

## Limitações conhecidas

- O modo automático desta fase escolhe o modelo preferido se estiver disponível; caso contrário, escolhe o nome em ordem estável. Não faz classificação semântica.
- O histórico local usa JSON; banco de dados e migrações serão avaliados conforme escala.
- O preflight do chat Ollama aplica `num_ctx` e `num_thread` ao payload por requisição; GPU/CPU placement e concorrência global permanecem sob controle do servidor Ollama e precisam de validação com serviço real.
- O monitor periódico existe, mas só inicia quando o chamador executa start(); a aplicação ainda não o inicia nem possui executor automático para descarregar modelos, pausar filas ou alterar concorrência.
- A detecção GPU atual é opcional e limitada a nvidia-smi e Linux DRM/sysfs; dispositivos identificados não significam que um backend acelerado esteja pronto.
- Quantização é somente uma política de seleção de candidatos. O código ainda não converte pesos, baixa variantes ou faz offloading manual.
- `engines/llama_cpp_options.py` constrói instância llama-cpp-python com contexto/threads do orçamento e GPU layers explicitamente validados; ainda não existe EngineAdapter llama.cpp completo nem integração na interface.
- A interface foi construída, mas precisa ser validada em sessão gráfica Linux/Qt.
- Os testes foram escritos; a execução da suíte depende de ambiente com as dependências instaladas.
