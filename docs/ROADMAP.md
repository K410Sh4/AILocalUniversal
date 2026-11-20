# Roadmap do AILocal Universal

As fases são entregas progressivas. Uma funcionalidade só é considerada concluída quando código, testes, documentação e validação no ambiente-alvo correspondem ao escopo declarado.

## Fase 0 — Fundação

- [x] Repositório, visão de produto e princípios local-first.
- [x] Estrutura Python modular e contratos iniciais.
- [x] Documentação de arquitetura, segurança e roadmap.

**Saída:** base versionada e extensível.

## Fase 1 — Aplicação desktop local

- [x] Interface PySide6 com Chat, Modelos e configurações.
- [x] Contrato Engine Adapter e registry.
- [x] Adaptador Ollama: health check, inventário, capacidades via API /api/show e streaming NDJSON.
- [x] Workers Qt para manter operações de rede fora da thread da interface.
- [x] Seleção manual/automática e modelo preferido.
- [x] Histórico e configuração locais com escrita atômica.
- [x] Cancelamento cooperativo, tratamento de erros e timeouts.
- [x] Validação visual do Chat, inventário e geração real com Ollama no Arch Linux, demonstrada nesta sessão.

**Saída:** aplicação local funcional com backend Ollama. A validação do executor/validação é feita separadamente na Fase 2.

## Fase 2 — Núcleo cognitivo e execução controlada

### 2.1 — Análise e planejamento

- [x] Input Processing com preservação da entrada original.
- [x] Semantic Analysis heurística.
- [x] Capability Vectorizer lexical de 12 dimensões.
- [x] Task Decomposer para listas e sequências explícitas.
- [x] Cognitive Planner, Orchestrator e Execution Trace.
- [x] Ferramentas determinísticas iniciais: calculadora AST restrita e conversor de unidades.

### 2.2 — Execução de subtarefas

- [x] Cognitive Inspector com análise, plano, subtarefas e trace.
- [x] Cognitive Task Executor sequencial, em worker Qt.
- [x] Ordenação topológica e bloqueio de dependências inválidas/cíclicas.
- [x] Execução local de cálculo/conversão quando intenção e risco permitem.
- [x] Chamadas individuais ao mesmo modelo para subtarefas LLM.
- [x] Síntese final com streaming para o Chat.
- [x] Estados explícitos para pendente, em execução, concluída, falha, bloqueada, cancelada e ignorada.

### 2.3 — Validation Layer

- [x] Conferência de resultado não vazio e estrutura da subtarefa.
- [x] Conferência das dependências antes de liberar resultados às etapas seguintes.
- [x] Reprodução determinística de cálculos/conversões e comparação de ferramenta, conteúdo, estado e valor.
- [x] Verificação de completude antes da síntese final.
- [x] Relatório estruturado no CognitiveTask e no Cognitive Inspector.
- [x] Separação entre aprovação estrutural, resultado reproduzido localmente e revisão factual pendente.
- [ ] Validar a nova camada no Arch Linux com pedidos determinísticos e compostos.
- [ ] Melhorar a decomposição de pedidos mistos para reduzir repetição de contexto nas subtarefas.

**Limite declarado:** saídas livres do LLM continuam como not_independently_verified. A camada atual não faz checagem factual geral, prova formal ou validação científica de explicações. Não há correção automática de conteúdo factual incerto; erros estruturais/determinísticos bloqueiam a síntese.

**Critério de saída da Fase 2:** testes locais aprovados, validação real no Arch, cancelamento/falhas conferidos e qualidade da decomposição revisada.

## Fase 3 — Conhecimento local e RAG verificável

### 3.1 — Ingestão e recuperação lexical (base inicial na branch `feature/rag-v1`)

- [x] Loader UTF-8 para texto e formatos técnicos declarados.
- [x] Loader Markdown com preservação de títulos e blocos.
- [x] Loader PDF opcional por pypdf, com limite de bytes/páginas/caracteres; sem OCR.
- [x] Proveniência com URI, SHA-256, página, seção e offsets Unicode.
- [x] Chunking determinístico com limites, sobreposição e separação por página/seção.
- [x] Índice lexical local SQLite FTS5, filtros por documento e reingestão sem resultados obsoletos.
- [x] Contratos substituíveis para busca vetorial e reranking.
- [x] Fusão de rankings por Reciprocal Rank Fusion quando o backend vetorial existe.
- [x] Context Composer com citações e orçamento em caracteres.
- [x] Validação estrutural de referências, hash e trecho original.
- [x] Testes unitários de loaders, chunking, indexação, recuperação, contexto e proveniência.

### 3.2 — Recuperação semântica e integração

- [x] Provedor de embeddings via Ollama `/api/embed`, com batch, dimensões configuráveis e rejeição de entradas excessivas sem truncamento silencioso.
- [x] Armazenamento vetorial SQLite com vetores float32 normalizados, busca cosseno, filtros e substituição transacional de documentos.
- [x] LocalVectorIndexer e backend vetorial que confere chunk_id, document_id e source_sha256 antes de devolver evidências.
- [x] Fusão lexical/vetorial por RRF quando o backend vetorial é fornecido.
- [x] Testes simulados do provider, persistência, filtros, reindexação e integração lexical/vetorial.
- [ ] Escolher e comparar modelos de embeddings locais em hardware leve, intermediário e potente.
- [ ] Implementar reranker concreto, opcional e mensurável.
- [ ] Definir política de deduplicação e orçamento de tokens com benchmarks.
- [ ] Validar ingestão e busca vetorial com Ollama real no Arch Linux.
- [ ] Integrar loaders/ingestor/retriever ao CognitiveTask e ao Cognitive Pipeline.
- [ ] Integrar Context Composer ao prompt do modelo e transportar Evidence para a Validation Layer.
- [ ] Exibir fontes, páginas e citações no Chat e no Cognitive Inspector.
- [ ] Criar corpus de avaliação RAG: precisão@k, recall@k, MRR, cobertura, fidelidade e conflitos.
- [ ] Avaliar resistência a prompt injection em documentos e a conteúdo adversarial.
- [ ] Definir orçamento de tokens por tokenizer/backend; a primeira versão usa limite em caracteres.

**Saída da Fase 3:** respostas com evidências recuperadas, proveniência verificável e validação explícita dos vínculos. A validação de links/hash não deve ser confundida com prova factual ou verificação de entailment.

## Fase 4 — Gerenciamento adaptativo de recursos

1. Telemetria de RAM, VRAM, CPU, GPU e disco, distinguindo valores disponíveis e estimados.
2. Perfil de hardware e orçamento realista de pesos, cache KV, contexto e buffers.
3. Model Manager: inventário, carregamento, descarregamento, estado quente/frio e leases.
4. Scheduler com fila, prioridade, concorrência limitada e cancelamento.
5. Políticas LRU e prevenção de thrashing entre modelos.
6. Enforcement de token budget, RAM budget e deadlines.
7. Benchmarks por hardware, modelo, quantização, contexto e estado frio/quente.

**Saída:** execução previsível dentro dos limites físicos da máquina.

## Fase 5 — Modelos especialistas e roteamento adaptativo

1. Perfis de capacidade por modelo, baseados em metadados verificáveis e benchmarks locais.
2. Corpus de avaliação por domínio: código, matemática, ciência, escrita e raciocínio.
3. Medição de qualidade, latência, memória e custo por tarefa.
4. Seletor que combine intenção, requisitos, perfil do modelo, recursos disponíveis e preferência do usuário.
5. Planejamento multi-modelo com justificativa e fallback explícito.
6. Síntese cruzada e validação de divergências entre especialistas.
7. Garantia de que a seleção manual do usuário prevaleça quando exigida.

**Saída:** roteamento especializado mensurável, explicável e reversível.

## Fase 6 — Rede cooperativa (Swarm P2P)

1. Identidade, pareamento e autorização explícita de nós.
2. Descoberta, heartbeat e telemetria.
3. Control Plane separado do Data Plane.
4. Transporte autenticado e criptografado, limites de tamanho, timeout e cancelamento.
5. Despacho de subtarefas independentes e Map-Reduce.
6. Transferência de arquivos com hash, integridade, retomada e controle de acesso.
7. Tolerância a falhas, nós offline e reconciliação de resultados.

**Saída:** cooperação entre máquinas confiáveis, sem presumir que descoberta equivale a autorização.

## Fase 7 — Laboratório de desempenho e backends experimentais

- BitNet e modelos de baixa precisão.
- llama.cpp RPC e execução remota experimental.
- Speculative decoding.
- Inferência distribuída por camadas apenas após benchmark de rede e memória.
- Comparação de qualidade, latência, throughput, consumo e estabilidade.

**Saída:** otimizações aceitas por evidência experimental, não por promessa teórica.

## Regras de evolução transversais

- Não confundir score heurístico com probabilidade.
- Não marcar saída de LLM como verificada sem evidência ou validador independente.
- Toda ferramenta precisa de contrato, limites, testes positivos e negativos.
- Toda tarefa distribuída exige autenticação, autorização, timeout, integridade e cancelamento.
- Benchmarks devem registrar hardware, modelo, quantização, contexto e estado quente/frio.
- main só recebe uma fase depois de revisão, CI aprovado e validação de aceitação no ambiente-alvo.
