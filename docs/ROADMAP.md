# Roadmap

As fases representam entregas e validações progressivas. Um componente só será considerado concluído após código, testes e critérios de aceitação.

## Fase 0 — Fundação

- [x] Repositório e visão inicial.
- [x] Estrutura modular mínima e contratos iniciais.
- [x] Documentação de arquitetura, segurança e roadmap.

## Fase 1 — Aplicação local (implementação inicial criada)

- [x] Janela PySide6 com Chat e Modelos.
- [x] Engine Adapter e registry.
- [x] Adaptador Ollama para health check, inventário e streaming NDJSON.
- [x] Workers Qt para operações de rede fora da thread de UI.
- [x] Cancelamento cooperativo de geração.
- [x] Seleção manual e modo automático determinístico.
- [x] Modelo preferido.
- [x] Configurações e histórico em JSON local com escrita atômica.
- [x] Tratamento inicial de falhas e timeouts.
- [x] Testes com transporte HTTP simulado.
- [ ] Validar visualmente e executar a suíte em Linux/Arch Linux.
- [ ] Validar geração e cancelamento contra um serviço Ollama real.

**Saída:** aplicação desktop local funcional após validação no ambiente-alvo.

## Fase 2 — Núcleo cognitivo

- Input Processing.
- Semantic Analysis.
- Capability Vectorizer calibrável.
- Ferramentas determinísticas.
- Cognitive Planner.
- Orchestrator com trace e rotas adaptativas.

## Fase 3 — Conhecimento e validação

- Loaders, parsers, chunking e embeddings.
- Busca híbrida e reranking.
- Context Composer com proveniência.
- Validação de evidências.

## Fase 4 — Recursos adaptativos

- Monitoramento RAM/VRAM/CPU/GPU.
- Model Manager.
- Orçamento de contexto/memória.
- Scheduler e limites de concorrência.

## Fase 5 — Rede cooperativa

- Identidade e pareamento.
- Descoberta e telemetria.
- Transporte autenticado e criptografado.
- Protocolo com limites, timeout e cancelamento.
- Map-Reduce e sincronização.

## Fase 6 — Laboratório

- BitNet.
- RPC.
- Inferência distribuída experimental.
- Speculative decoding.
- Otimização multi-host.

## Trilha proposta — NeuralPlugin / NeuralInjector

- [x] Definir cinco perfis canônicos, orçamento de recursos, benchmark opt-in e degradação graciosa.
- [x] Tornar Python a fonte canônica dos perfis e verificar a sincronização dos JSON por testes e script de geração.
- [x] Adicionar detecção opcional de GPU (NVIDIA via nvidia-smi e Linux DRM/sysfs), separada do registro de backends executáveis.
- [x] Adicionar políticas declarativas de quantização, seleção condicionada às capacidades reportadas pelo backend e modos permissive/adaptive/protected.
- [x] Adicionar avaliador de pressão de memória com histerese e recomendações que não interrompem gerações em andamento.
- [x] Adicionar monitor periódico opt-in, com callback, provedor substituível e início explícito.
- [x] Adicionar ao adaptador Ollama telemetria (/api/ps) e tradução do orçamento para num_ctx/num_thread por requisição.
- [x] Integrar preflight de recursos ao fluxo de chat e expor perfil/modo de proteção nas Configurações.
- [x] Implementar recusa de piso absoluto de 1,5 GiB com explicação e recomendações no diálogo.
- [ ] Integrar o monitor ao ciclo de vida da aplicação, incluindo amostragem de VRAM por provedor e executor seguro das ações recomendadas.
- [ ] Criar EngineAdapter llama.cpp completo; o mapeador de opções do construtor já está coberto por testes.
- [ ] Implementar resolução de artefatos quantizados e offloading somente quando o backend oferecer suporte explícito.
- [ ] Validar testes e benchmarks em hardware leve, intermediário e potente.

Esta trilha foi adicionada como proposta documental e **não altera o compromisso nem o estado das Fases 0 a 6**. A implementação depende de revisão da especificação, decisões de compatibilidade e critérios de segurança.

- [ ] Revisar e estabilizar a NIP 0.1.0.
- [ ] Implementar parser de manifesto e validação por JSON Schema.
- [ ] Implementar leitura ZIP64 com limites e proteção contra traversal.
- [ ] Implementar verificação SHA-256 e suporte a assinatura confiável.
- [ ] Criar NeuralPlugin Manager com importação em modo dry-run, ativação, desativação e rollback.
- [ ] Compor regras por modelo com prioridades, dependências e detecção de conflitos.
- [ ] Integrar adaptadores apenas nos backends que declararem suporte.
- [ ] Integrar seleção adaptativa ao runtime/backend e adicionar benchmarks reproduzíveis. (Planejador inicial já adicionado.)
- [ ] Pesquisar transformações estruturais e restauração com validação de arquitetura/tensores.

Documentação: [NeuralPlugin Manager](NEURALPLUGIN.md), [NIP 0.1.0](NEURALINJECTOR_NIP_0.1.0.md), [schemas](../schemas/) e [exemplo](../examples/neuralinjector/).

## Critérios transversais

Cada entrega inclui testes, documentação, tratamento de erros e métricas. Benchmarks informam hardware, modelo, quantização, contexto e estado frio/quente.


## Trilha experimental — Workflow Graph / NeuralMap

- [x] Definir formato versionado `ailocal.pipeline-graph` e JSON Schema.
- [x] Criar modelo Python de nós, portas, arestas e layout.
- [x] Validar portas, referências, requisitos de entrada, caminhos input/output e ciclos não controlados.
- [x] Implementar runtime assíncrono, handlers allowlisted, trace e cancelamento.
- [x] Implementar loop de revisão limitado, feedback direcionado e fallback para melhor score.
- [x] Criar template multi-especialista com Qwen, DeepSeek e nó de imagem opcional.
- [x] Criar primeira aba NeuralMap com canvas, zoom/pan, biblioteca, propriedades, conexões condicionais e undo/redo.
- [x] Integrar worker Qt e execução dry-run/real.
- [x] Adicionar persistência do grafo em pacote .neuralinjector com verificação SHA-256 e referência no manifesto.
- [ ] Integrar e validar backend real de imagem (Flux ou equivalente) e armazenamento de artefatos.
- [ ] Adicionar anexos à UI e ao fluxo de especialistas.
- [ ] Renderizar resultado estruturado no ChatView (código, Markdown e imagem).
- [ ] Finalizar UX de exclusão/realce e validar visualmente no Linux/Arch.
- [ ] Executar pytest/Ruff e validar fluxo com Ollama real antes de considerar a entrega aceita.

Documentação: [NeuralMap](NEURALMAP.md), [schema de pipeline](../schemas/pipeline-graph.schema.json) e [template](../examples/workflows/multi_specialist.pipeline.graph.json).

A implementação está isolada na branch `feature/neuralmap-v1`; não altera nem mescla `main`.
