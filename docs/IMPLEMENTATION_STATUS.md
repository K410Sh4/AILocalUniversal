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
| RAG / Context Composer | Base lexical/vetorial, KnowledgeRuntime e aba Conhecimento implementados na `feature/rag-v1`; smoke test real no Arch aprovado com Ollama `embeddinggemma` (768 dimensões); CI atual: 142 testes | Sem chamada do KnowledgeRuntime pelo MainWindow/CognitiveTaskExecutor, citações no Chat, reranker concreto, UI Chat-RAG, avaliação em corpus real, OCR ou verificação factual/entailment |
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
- validação estrutural de vínculos, hashes e trechos citados;
- script de smoke test para `/api/embed` e recuperação vetorial no Ollama real com dados sintéticos e SQLite temporário;
- `KnowledgeLibrary` para persistência, ingestão, consulta, exclusão do índice e reindexação por modelo;
- aba PySide6 **Conhecimento**, com seleção de arquivos, listagem, remoção do índice e prévia de recuperação;
- workers Qt para operações da biblioteca sem bloquear a thread da interface;
- seleção persistente de modelo de embeddings separada do modelo de chat;
- bancos SQLite em diretório local privado, sem mover ou excluir arquivos originais;

Validação operacional no Arch Linux concluída para o caminho básico de embeddings e recuperação: Python 3.14, `pytest` com 132 testes aprovados antes da nova UI, Ollama `embeddinggemma`, dimensão 768, dois chunks sintéticos, busca vetorial e híbrida aprovadas e banco temporário removido. A branch atual passou no CI com Ruff e 142 testes Pytest (Python 3.11). A nova aba e os fluxos de gestão ainda aguardam validação visual/operacional no Arch. O `top_cosine_similarity` foi 1.0 para a consulta idêntica. Essa validação não mede qualidade semântica em corpus real. A aba Conhecimento gerencia arquivos e prévia de busca, mas não chama o KnowledgeRuntime no MainWindow/CognitiveTaskExecutor nem injeta resultados no Chat. Não há reranker concreto, OCR ou fontes/citações renderizadas na conversa. A verificação de citações não garante que alegações do modelo sejam consequência lógica das fontes.

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
- Chamada do KnowledgeRuntime pelo MainWindow/CognitiveTaskExecutor e integração RAG no Chat, exibição de fontes/citações na conversa, reranker concreto, avaliação RAG em corpus real, OCR, gerenciamento adaptativo de recursos, roteamento multi-modelo e Swarm ainda não foram implementados. A aba Conhecimento implementada ainda precisa de validação visual no Arch.
- O renderizador matemático cobre um subconjunto de LaTeX, não um motor TeX completo.
- O orçamento de tokens atual é indicativo e ainda não é aplicado como limite efetivo da engine.

## Validação operacional

O usuário já demonstrou no Arch Linux/KDE o Chat com Ollama/Qwen, o inventário de modelos, a decomposição de pedidos, a execução sequencial e a rota de calculadora local + explicação pelo modelo. A Validation Layer desta entrega ainda precisa ser exercitada no ambiente-alvo com:
1. cálculo determinístico direto;
2. pedido composto cálculo + explicação;
3. explicação científica com aviso de revisão factual;
4. falha/cancelamento durante execução.


## Registro de validação operacional — 2026-11-20

Resultado informado e executado pelo usuário no Arch Linux:
- Python: 3.14.
- Pytest: 132 testes aprovados.
- Modelo de embeddings: `embeddinggemma`.
- Dimensão retornada: 768.
- Chunks sintéticos indexados: 2.
- Resultados vetoriais: 2.
- Resultados híbridos: 2.
- Similaridade cosseno do primeiro resultado para a consulta idêntica: 1.0.
- Armazenamento: SQLite temporário removido ao final.
- Origem dos documentos: dados sintéticos; nenhum documento pessoal foi ingerido.

Esse resultado comprova conectividade e execução do caminho técnico básico no ambiente-alvo. Não é benchmark de precisão/recall, nem valida a qualidade de respostas RAG em documentos reais.

O aviso de depreciação do pytest-asyncio foi tratado pela configuração explícita `asyncio_default_fixture_loop_scope = "function"` em `pyproject.toml`.


## Fase 3.3 — Biblioteca documental e aba Conhecimento

Implementado na branch `feature/rag-v1`:
- Serviço `KnowledgeLibrary` em diretório XDG de dados, com bancos SQLite lexical e vetorial.
- Seleção explícita de TXT, Markdown, PDF e formatos técnicos suportados.
- Listagem de documentos e contagem de chunks.
- Exclusão da entrada documental e vetores do índice, sem apagar o arquivo original.
- Prévia de busca híbrida; se embeddings falharem durante a consulta, a biblioteca tenta busca lexical e informa o aviso.
- Modelo de embeddings escolhido separadamente, salvo na configuração.
- Reindexação explícita de documentos existentes ao trocar de modelo.
- Worker Qt para listagem, ingestão, remoção, busca e reindexação.
- Diretórios privados (0700) e arquivos SQLite privados (0600) no Linux.

Validação automatizada atual: Ruff aprovado e 142 testes Pytest aprovados no CI. A validação visual e a execução de ingestão/remoção de um documento de teste no Arch ainda estão pendentes. O Chat não consome esses documentos automaticamente.
