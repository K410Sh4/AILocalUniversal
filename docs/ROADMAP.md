# Roadmap do AILocal Universal

As fases são entregas progressivas. Uma funcionalidade só é considerada concluída quando código, testes, documentação e validação no ambiente-alvo correspondem ao escopo declarado.

## Fase 0 — Fundação

- [x] Repositório, visão de produto e princípios local-first.
- [x] Estrutura Python modular e contratos iniciais.
- [x] Documentação de arquitetura, segurança e roadmap.

## Fase 1 — Aplicação desktop local

- [x] Interface PySide6 com Chat, Modelos e configurações.
- [x] Contrato Engine Adapter e registry.
- [x] Adaptador Ollama: health, inventário, capacidades via /api/show e streaming NDJSON.
- [x] Workers Qt, seleção manual/automática, histórico e configuração local.
- [x] Cancelamento cooperativo, timeouts e tratamento de erros.
- [x] Validação visual do Chat, inventário e geração real no Arch Linux.

## Fase 2 — Núcleo cognitivo e execução controlada

- [x] Input Processing, Semantic Analysis heurística e Capability Vectorizer lexical.
- [x] Task Decomposer, Cognitive Planner, Orchestrator e Execution Trace.
- [x] Ferramentas determinísticas iniciais: calculadora AST restrita e conversor de unidades.
- [x] Cognitive Inspector e Cognitive Task Executor sequencial em worker Qt.
- [x] Estados explícitos, ordenação topológica e bloqueio de dependências inválidas/cíclicas.
- [x] Validation Layer estrutural e replay determinístico de ferramentas.

**Limite:** saídas livres do LLM permanecem não verificadas factualmente; a Validation Layer não substitui prova formal ou verificação de domínio.

## Fase 3 — Conhecimento local e RAG verificável

- [x] Loaders explícitos para texto, Markdown, formatos técnicos e PDF opcional.
- [x] Proveniência por URI, SHA-256, página, seção e offsets Unicode.
- [x] Chunking determinístico e índice lexical SQLite FTS5.
- [x] Embeddings via Ollama, SQLite vetorial e recuperação híbrida por RRF.
- [x] Context Composer, validação estrutural de citações e KnowledgeRuntime.
- [x] Biblioteca local privada e aba Conhecimento com workers Qt.
- [x] Integração opt-in do RAG ao Chat, fontes na resposta e evidências no Cognitive Inspector.
- [x] EmbeddingGemma e Qwen3 Embedding testados no Arch.
- [x] Ruff e 155 testes Pytest; Chat com RAG ligado/desligado e Cognitive Inspector validados.
- [x] Microbenchmark sintético: ambos embeddings acertaram o documento esperado em primeiro lugar nas quatro consultas; baseline lexical não recuperou as formulações sem sobreposição lexical.

**Limites desta entrega:** reranker concreto, corpus representativo com julgamento humano, OCR, orçamento efetivo por tokenizer e verificação semântica independente permanecem futuros. O microbenchmark sintético não estabelece um vencedor entre os embeddings nem prevê qualidade em corpus real.

## Fase 4 — NeuralModel Hub e gerenciamento adaptativo

### 4.1 — Registro e descoberta (implementado nesta branch; validação pendente)

- [x] Contrato versionável de ficha de modelo, artefato/runtime, licença e requisitos.
- [x] Registro JSON local com escrita atômica, versão de esquema e permissões restritas no Linux.
- [x] Descoberta do inventário Ollama sem inferir metadados ausentes.
- [x] Preservação de metadados curados durante sincronização do runtime.
- [x] Interface inicial NeuralModel Hub integrada à aplicação.
- [ ] Validar a interface e a persistência no Arch Linux.

### 4.2 — Hardware Compatibility Engine (implementação inicial nesta branch)

- [x] Perfil de CPU, RAM, disco e GPUs Linux via sysfs DRM.
- [x] Leitura de VRAM total/usada/livre e driver quando expostos pelo kernel.
- [x] Estados compatível/incompatível/não avaliado baseados em requisitos verificados.
- [ ] Validar medições na RX 5700 XT e em ambiente sem GPU dedicada.
- [ ] Ampliar probes por plataforma/runtime; fabricante e driver não comprovam Vulkan/ROCm/CUDA.

### 4.3 — Adaptive Model Selector (planejado)

- [ ] Catálogo curado e fontes externas com procedência por campo e licença por versão/artefato.
- [ ] Requisitos de memória por modelo, quantização, runtime, contexto e offload, baseados em evidência ou medição.
- [ ] Benchmark local de qualidade, latência, RAM/VRAM e estabilidade.
- [ ] Seleção por tarefa, recursos, preferência, qualidade medida e fallback explicável.
- [ ] Políticas de carregamento, descarregamento, leases e concorrência integradas ao Resource Manager.
- [ ] Download/instalação somente com consentimento, licença, integridade e espaço em disco verificados.

**Saída:** descoberta e seleção de modelos explicáveis, conservadoras e adaptadas ao hardware real.

## Fase 5 — Agentes especialistas e autoengenharia

- [ ] System Analyst em modo somente leitura.
- [ ] Code Analyst para análise do repositório e dependências.
- [ ] Test Engineer para reproduzir falhas e executar testes autorizados.
- [ ] Security Auditor com escopo e ferramentas restritos.
- [ ] Implementer em branch/worktree isolado, diff revisável e testes.
- [ ] Validação independente e aprovação humana antes de qualquer merge.

**Saída:** agentes especializados que analisam e propõem mudanças sem modificar main autonomamente.

## Fase 6 — Rede cooperativa (Swarm P2P)

- [ ] Identidade, pareamento e autorização explícita de nós.
- [ ] Descoberta, heartbeat e telemetria.
- [ ] Control Plane separado do Data Plane.
- [ ] Transporte autenticado e criptografado, limites, timeout e cancelamento.
- [ ] Despacho de subtarefas independentes e Map-Reduce.
- [ ] Transferência de arquivos com hash, integridade, retomada e controle de acesso.
- [ ] Tolerância a falhas, nós offline e reconciliação de resultados.

## Fase 7 — Laboratório de desempenho e backends experimentais

- [ ] BitNet e modelos de baixa precisão.
- [ ] llama.cpp RPC e execução remota experimental.
- [ ] Speculative decoding.
- [ ] Inferência distribuída por camadas após benchmark de rede e memória.
- [ ] Comparação de qualidade, latência, throughput, consumo e estabilidade.

## Regras transversais

- Não confundir score heurístico com probabilidade.
- Não marcar saída de LLM como verificada sem evidência ou validador independente.
- Toda ferramenta precisa de contrato, limites e testes positivos/negativos.
- Toda tarefa distribuída exige autenticação, autorização, timeout, integridade e cancelamento.
- Benchmarks registram hardware, modelo, quantização, contexto e estado quente/frio.
- main só recebe uma fase depois de revisão, CI aprovado e validação de aceitação no ambiente-alvo.
