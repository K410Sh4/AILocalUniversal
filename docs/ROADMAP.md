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

## Critérios transversais

Cada entrega inclui testes, documentação, tratamento de erros e métricas. Benchmarks informam hardware, modelo, quantização, contexto e estado frio/quente.
