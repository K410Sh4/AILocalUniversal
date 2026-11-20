# RAG local — especificação da primeira entrega

## Objetivo

Construir uma camada local e rastreável de ingestão e recuperação, com integração ao Chat ativada apenas por escolha explícita do usuário. A implementação está isolada na branch `feature/rag-v1` e ainda não altera a `main`.

## Fluxo implementado

~~~mermaid
flowchart TD
  A[Arquivo escolhido pelo usuário] --> B[Loader local]
  B --> C[SHA-256 + metadados]
  C --> D[Texto / páginas]
  D --> E[Chunker]
  E --> F[SQLite FTS5]
  E --> G[Ollama Embedding API]
  G --> H[SQLite Vector Store]
  F --> I[Retriever lexical]
  H --> J[Retriever vetorial]
  I --> K[RRF]
  J --> K
  K --> L[Context Composer]
  L --> M[Evidence + citações]
  M --> N[Evidence Validator]
~~~

## Ingestão suportada

- TXT e formatos técnicos declarados: UTF-8.
- Markdown: UTF-8, títulos e blocos preservados como limites de chunking.
- PDF: extração de texto selecionável por pypdf opcional. PDFs criptografados são rejeitados; OCR não existe nesta entrega.
- Limites padrão: 20 MiB por arquivo, 2 milhões de caracteres extraídos e 500 páginas por PDF. Os limites podem ser ajustados na construção do loader.
- A ingestão é explícita: o usuário fornece o arquivo. Não há varredura automática do disco, download de documentos ou execução de conteúdo.

## Proveniência

Cada documento registra URI local e SHA-256 dos bytes originais. Cada chunk mantém digest da origem, offsets Unicode do texto extraído, número de página quando aplicável e caminho de seção Markdown. Para PDFs, offsets são relativos ao texto extraído da página, não aos bytes nem à posição visual no PDF.

O identificador do documento é estável por URI. Reingestão do mesmo caminho substitui a versão lexical indexada. Ao indexar embeddings, `LocalVectorIndexer` substitui os vetores dos documentos fornecidos para o modelo selecionado, removendo chunks vetoriais obsoletos desses documentos.

## Recuperação lexical e vetorial

SQLite FTS5 fornece busca lexical local e filtros por document_id. O tokenizador Unicode remove diacríticos para facilitar pesquisas em português. A consulta remove palavras funcionais comuns em português/inglês e exige correspondência de todos os termos restantes. Termos de negação como “não” e “sem” são preservados.

`OllamaEmbeddingProvider` envia lotes de textos ao endpoint `POST /api/embed`. O modelo de embeddings é definido explicitamente e deve estar instalado no Ollama. O padrão de conexão é `http://127.0.0.1:11434`; a URL pode ser configurada. O provedor valida quantidade de vetores, dimensões, componentes numéricos e valores finitos. O padrão `truncate=False` evita truncamento silencioso de entradas longas.

`SQLiteVectorStore` persiste vetores float32 normalizados e ordena por similaridade cosseno. Os registros incluem model_name, dimensões, chunk_id, document_id e hash da origem. O armazenamento é local; os vetores são substituíveis por modelo. O backend descarta correspondências cujo chunk não existe mais no índice lexical ou cujo hash diverge.

`HybridRetriever` combina ranking lexical e vetorial usando Reciprocal Rank Fusion. A fusão só usa a busca vetorial quando um backend vetorial é fornecido. O contrato para reranking existe, mas ainda não há reranker concreto. Scores são sinais de ordenação, não probabilidades.

## Smoke test com Ollama real

Depois de instalar um modelo de embeddings, execute:

~~~bash
ollama pull embeddinggemma
.venv/bin/python scripts/smoke_test_embeddings.py --model embeddinggemma
~~~

O script usa dois textos sintéticos, SQLite temporário e uma consulta idêntica a um dos trechos. Em 2026-11-20, o usuário executou o teste no Arch Linux com `embeddinggemma`: resultado `passed`, dimensão 768, 2 chunks indexados, 2 resultados vetoriais, 2 híbridos, similaridade cosseno 1.0 para a consulta idêntica e armazenamento temporário removido. Não lê nem envia documentos pessoais. Não é benchmark de qualidade, nem substitui testes com documentos reais. O nome do modelo é exemplo e pode ser trocado por outro modelo de embeddings compatível.


## Context Composer e validação

O Context Composer gera marcadores `[E1]`, `[E2]` etc., adiciona origem e localizador e preserva Evidence compatível com `core.cognitive_task.Evidence`. O orçamento é explicitamente em caracteres Unicode, não tokens. Trechos que não cabem são omitidos integralmente e seus IDs aparecem em skipped_chunk_ids; evidências não são truncadas silenciosamente.

EvidenceValidator confere se as citações remetem a chunks existentes e se hash, conteúdo e offsets coincidem com o índice. Seu factual_status continua `not_independently_verified`: integridade do link não demonstra entailment, ausência de contradição nem verdade factual da resposta.

## Biblioteca documental e aba Conhecimento

`KnowledgeLibrary` fornece persistência e gestão da biblioteca no diretório:

`$XDG_DATA_HOME/ailocal-universal/knowledge`

Na ausência de `XDG_DATA_HOME`, utiliza `~/.local/share/ailocal-universal/knowledge`. No Linux, o diretório e os bancos são criados com permissões privadas (0700 para diretórios e 0600 para arquivos SQLite).

A aba PySide6 **Conhecimento** oferece:
- seleção explícita de arquivos TXT, Markdown, PDF e formatos técnicos suportados;
- ingestão lexical e, quando há um modelo selecionado, indexação vetorial;
- listagem de documentos, tipo, tamanho e contagem de trechos;
- remoção do documento do índice lexical/vetorial, sem apagar ou mover o original;
- prévia da recuperação e das fontes antes de qualquer uso no Chat;
- seleção persistente de modelo de embeddings, separada do modelo de chat;
- ação explícita para reindexar vetores após a troca do modelo.

As operações de armazenamento e inferência são executadas em workers Qt. Se a geração de embeddings falhar durante a ingestão, a versão lexical permanece e a UI informa que a indexação foi parcial. Se a busca vetorial falhar na consulta, a biblioteca tenta a busca lexical e mostra um aviso. A reindexação é necessária para que documentos existentes tenham vetores no novo modelo escolhido.

A aba Conhecimento administra a biblioteca e permite prévia de busca. Separadamente, o Chat oferece o controle explícito `Usar conhecimento local`, desativado por padrão; quando ativado, recupera evidências antes de chamar o modelo.

## Ponte para o CognitiveTask

`KnowledgeRuntime` é a camada de ligação explícita entre recuperação e tarefa cognitiva:

- executa a recuperação com filtro de documento e orçamento de contexto;
- anexa os objetos `Evidence` resultantes ao `CognitiveTask`, evitando duplicar chunk_id já associado;
- registra no plano e no trace apenas contagens/localizadores técnicos, sem copiar o conteúdo sensível dos documentos para o log;
- prepara uma mensagem de contexto em papel `user`, delimitada como material documental não confiável e orienta o modelo a não obedecer instruções contidas nas fontes;
- expõe a validação estrutural das citações.

Esta ponte é chamada pelo `MainWindow` no fluxo de mensagens quando o usuário ativa o RAG. A recuperação acontece antes da seleção/execução do modelo de chat e o mesmo contexto é passado ao executor sequencial quando a tarefa possui subtarefas.

## Limites desta entrega

- O RAG no Chat é opt-in e permanece desativado por padrão. A recuperação roda em worker Qt e o fallback sem contexto local é registrado quando houver falha.
- Não há reranker concreto, OCR ou tratamento de PDF escaneado.
- O usuário deve instalar e selecionar um modelo de embeddings; a aplicação não baixa modelos automaticamente.
- O CI anterior à integração Chat incluía 142 testes. A integração e seus testes adicionais foram aprovados em CI com Ruff e 149 testes Pytest (Python 3.11). O usuário já validou no Arch a aba Conhecimento e recuperação vetorial com EmbeddingGemma e Qwen3 Embedding; o fluxo novo de Chat-RAG ainda aguarda teste operacional após pull. Ainda faltam benchmarks de qualidade em corpus representativo e avaliação factual/entailment.
- Embeddings de texto não são equivalentes a um verificador factual: recuperação e integridade de citações não garantem que uma alegação seja suportada pela fonte.

## Próximas entregas da Fase 3

1. Escolha e benchmark de modelos locais de embeddings em hardware leve, intermediário e potente.
2. Reranker concreto, opcional e avaliado por qualidade/latência.
3. Política de deduplicação, busca híbrida, filtros e orçamento por tokenizer/backend.
4. Integração ao Cognitive Pipeline, CognitiveTask e Validation Layer.
5. Benchmark de fontes/citações no Chat e no Cognitive Inspector com corpus representativo; a integração opt-in inicial já existe, mas ainda precisa de validação operacional após o pull.
6. Corpus de avaliação RAG com precision@k, recall@k, MRR, cobertura, fidelidade, conflitos e resistência a prompt injection.

Nenhuma dessas capacidades pendentes deve ser anunciada como concluída. A integração opt-in inicial ao Chat foi implementada; sua aceitação depende do CI atualizado e do teste operacional no Arch.


 
## Integração ao Chat e validação de citações

- O controle "Usar conhecimento local" é persistido em AppConfig.knowledge_enabled e permanece desativado por padrão, inclusive em configurações antigas.
- A recuperação é executada por KnowledgeRetrievalWorker, fora da thread da interface.
- Evidências são anexadas à CognitiveTask; plano/trace registra contagens e estado sem duplicar chunks.
- O conteúdo recuperado é fornecido como mensagem documental não confiável. O prompt orienta o modelo a citar identificadores existentes e a declarar insuficiência/conflito.
- Ao concluir, EvidenceValidator confere os identificadores citados e a relação entre evidência, chunk, hash, offsets e documento indexado.
- Fontes recuperadas são exibidas abaixo da resposta e a tabela de evidências aparece no Cognitive Inspector.
- Citações desconhecidas falham na validação estrutural; ausência de citação gera needs_review.
- factual_status permanece not_independently_verified: integridade do vínculo e hash não prova entailment ou verdade factual.

## Limites de conclusão da Fase 3

O núcleo lexical/vetorial, a biblioteca, a recuperação no Chat com ativação explícita e a exibição/validação estrutural das fontes compõem a entrega da Fase 3. Reranker concreto, benchmark de qualidade em corpus representativo, orçamento por tokenizer real, OCR e verificação semântica independente são evoluções posteriores; não são anunciados como concluídos nesta entrega.



## Benchmark sintético de recuperação

O script `scripts/evaluate_rag.py` cria quatro documentos sintéticos temporários e quatro consultas com documentos relevantes conhecidos. Mede precision@k, recall@k, MRR e cobertura em nível de documento, removendo IDs duplicados para que vários chunks do mesmo arquivo não contem como vários documentos.

Compare os modelos com as mesmas consultas:

~~~bash
.venv/bin/python scripts/evaluate_rag.py --model embeddinggemma:latest
.venv/bin/python scripts/evaluate_rag.py --model qwen3-embedding:0.6b
~~~

O script também pode executar o baseline lexical sem `--model`. Os resultados servem como microbenchmark reproduzível, não como evidência de qualidade em corpus real ou de veracidade factual. Os números dos modelos devem ser comparados pelas métricas de ranking, não pelos scores cosseno brutos entre espaços vetoriais diferentes.
