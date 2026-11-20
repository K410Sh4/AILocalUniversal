# Estado da implementação

Este documento diferencia código integrado, cobertura automatizada e validação operacional.

## Estado atual

| Área | Implementado | Limite / próximo passo |
|---|---|---|
| Interface PySide6 | Chat, Modelos, configurações e Cognitive Inspector | Refinamentos conforme validação visual no Arch |
| Engine Adapter | Contrato e registry | Novos backends em fases futuras |
| Ollama | Health, inventário, capacidades, NDJSON e streaming | Expandir testes de integração e erros de runtime |
| Storage | Histórico e configuração JSON, escrita atômica | Avaliar migração para banco conforme escala |
| CognitiveTask | Contrato versionado, serialização e relatório de validação | Migrações formais quando houver mudança incompatível |
| Input Processing | Normalização e preservação do original | Suporte posterior a anexos |
| Semantic Analysis | Intenção e indicadores heurísticos | Embeddings, calibração e avaliação |
| Capability Vectorizer | 12 dimensões lexicais explicáveis | Embeddings e classificador calibrado |
| Task Decomposer | Listas e conectores sequenciais explícitos | Melhor decomposição de pedidos mistos e não estruturados |
| Deterministic Tools | Calculadora AST restrita e conversor de unidades | Ampliar catálogo sob testes específicos |
| Cognitive Task Executor | Execução sequencial em worker, dependências, ferramenta local, subtarefas LLM e síntese | Sem paralelismo ou roteamento multi-modelo |
| Validation Layer | Estrutura, dependências, replay determinístico, completude e relatório | Sem verificação factual geral de texto LLM |
| Cognitive Inspector | Mostra resultados, estados, trace e relatório de validação | Mostra apenas a última tarefa da sessão |
| RAG / Context Composer | Parcial na branch `feature/rag-v1`: loaders TXT/Markdown/PDF, proveniência SHA-256, chunking, SQLite FTS5, embeddings Ollama `/api/embed`, armazenamento vetorial SQLite/cosseno, RRF, Context Composer, KnowledgeRuntime e validação estrutural de citações | Sem reranker concreto, OCR, chamada pelo MainWindow/CognitiveTaskExecutor, UI de documentos, avaliação de qualidade em corpus real ou validação operacional no Arch com Ollama real |
| Adaptive Resource Manager | Planejado | Fase 4 |
| Roteamento especialista | Planejado | Fase 5 |
| Swarm P2P | Planejado | Fase 6 |
| BitNet / RPC | Experimental futuro | Fase 7 |

## Fase 3 — escopo inicial em desenvolvimento

A branch `feature/rag-v1` contém uma primeira base executável de conhecimento local:
- loaders explícitos para TXT, Markdown e PDF; pypdf é opcional;
- proveniência por URI, SHA-256, página, seção e offsets;
- chunking determinístico com limites e sobreposição;
- índice lexical SQLite FTS5, com filtros e substituição de versões do mesmo arquivo;
- provedor de embeddings local via Ollama `/api/embed`, com batching e validação de dimensões;
- armazenamento vetorial SQLite com vetores float32 normalizados, busca cosseno e filtro por documento/modelo;
- indexador vetorial e backend de busca compatível com `HybridRetriever`, com checagem de hash no retorno;
- fusão RRF de rankings lexical/vetorial; reranker permanece apenas como contrato;
- KnowledgeRuntime para anexar Evidence ao CognitiveTask e preparar mensagem de contexto delimitada como dado documental não confiável;
- composição de contexto com citações estáveis e orçamento em caracteres;
- validação estrutural de vínculos, hashes e trechos citados.- validação estrutural de vínculos, hashes e trechos citados;
- script de smoke test para `/api/embed` e recuperação vetorial no Ollama real com dados sintéticos e SQLite temporário.

Há código e testes para embeddings Ollama, índice vetorial SQLite e ponte KnowledgeRuntime, mas ainda não houve validação com um servidor Ollama real no Arch. O MainWindow/CognitiveTaskExecutor ainda não chama o runtime; não há reranker concreto, OCR ou UI de documentos. A verificação de citações não garante que alegações do modelo sejam consequência lógica das fontes.

## Validation Layer: escopo atual

A camada atual executa verificações reproduzíveis:
- resultado não vazio e saída estruturalmente presente;
- dependências referenciadas e concluídas;
- replay local de calculadora/conversor;
- comparação de ferramenta, saída textual, estado de sucesso/erro e valor numérico;
- presença de resultados para todas as subtarefas e da síntese final.

Estados do relatório:
- passed: verificações executáveis passaram e não existem avisos de revisão;
- needs_review: estrutura passou, mas conteúdo gerado por LLM não foi verificado independentemente;
- failed: inconsistência estrutural/determinística bloqueia a aceitação;
- cancelled: execução interrompida antes da validação final.

verified_deterministic significa que a mesma ferramenta local reproduziu a operação e a saída; não é prova formal de todo o domínio matemático. not_independently_verified significa que o texto do LLM não foi confrontado com fontes externas ou um verificador de domínio.

## Limitações conhecidas

- Afinidades de capacidades e indicadores de dificuldade, incerteza, risco e urgência continuam heurísticos e não calibrados.
- A decomposição depende de listas e conectores explícitos; pedidos mistos podem carregar contexto redundante nas subtarefas.
- O executor é sequencial e usa o mesmo modelo em todas as subtarefas LLM e na síntese.
- A síntese final é produzida por LLM e permanece factualmente não verificada.
- A Validation Layer atual não prova teoremas, não verifica fatos gerais e não substitui validação de domínio.
- O conjunto de ferramentas determinísticas é pequeno e cobre somente expressões/unidades suportadas.
- O Cognitive Inspector mostra apenas a última tarefa da sessão; o relatório de validação não é persistido como histórico de execuções.
- Reranker concreto, chamada do KnowledgeRuntime pelo MainWindow/CognitiveTaskExecutor, UI de documentos, avaliação RAG em corpus real, validação com Ollama real no Arch, OCR, gerenciamento adaptativo de recursos, roteamento multi-modelo e Swarm ainda não foram implementados.
- O renderizador matemático cobre um subconjunto de LaTeX, não um motor TeX completo.
- O orçamento de tokens atual é indicativo e ainda não é aplicado como limite efetivo da engine.

## Validação operacional

O usuário já demonstrou no Arch Linux/KDE o Chat com Ollama/Qwen, o inventário de modelos, a decomposição de pedidos, a execução sequencial e a rota de calculadora local + explicação pelo modelo. A Validation Layer desta entrega ainda precisa ser exercitada no ambiente-alvo com:
1. cálculo determinístico direto;
2. pedido composto cálculo + explicação;
3. explicação científica com aviso de revisão factual;
4. falha/cancelamento durante execução.
