# RAG local — especificação da primeira entrega

## Objetivo

Construir uma camada local e rastreável de ingestão e recuperação antes de integrá-la ao prompt do Chat. A implementação está isolada na branch \`feature/rag-v1\` e ainda não altera a \`main\`.

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

O identificador do documento é estável por URI. Reingestão do mesmo caminho substitui a versão lexical indexada. Ao indexar embeddings, \`LocalVectorIndexer\` substitui os vetores dos documentos fornecidos para o modelo selecionado, removendo chunks vetoriais obsoletos desses documentos.

## Recuperação lexical e vetorial

SQLite FTS5 fornece busca lexical local e filtros por document_id. O tokenizador Unicode remove diacríticos para facilitar pesquisas em português. A consulta remove palavras funcionais comuns em português/inglês e exige correspondência de todos os termos restantes. Termos de negação como “não” e “sem” são preservados.

\`OllamaEmbeddingProvider\` envia lotes de textos ao endpoint \`POST /api/embed\`. O modelo de embeddings é definido explicitamente e deve estar instalado no Ollama. O padrão de conexão é \`http://127.0.0.1:11434\`; a URL pode ser configurada. O provedor valida quantidade de vetores, dimensões, componentes numéricos e valores finitos. O padrão \`truncate=False\` evita truncamento silencioso de entradas longas.

\`SQLiteVectorStore\` persiste vetores float32 normalizados e ordena por similaridade cosseno. Os registros incluem model_name, dimensões, chunk_id, document_id e hash da origem. O armazenamento é local; os vetores são substituíveis por modelo. O backend descarta correspondências cujo chunk não existe mais no índice lexical ou cujo hash diverge.

\`HybridRetriever\` combina ranking lexical e vetorial usando Reciprocal Rank Fusion. A fusão só usa a busca vetorial quando um backend vetorial é fornecido. O contrato para reranking existe, mas ainda não há reranker concreto. Scores são sinais de ordenação, não probabilidades.

## Smoke test com Ollama real

Depois de instalar um modelo de embeddings, execute:

~~~bash
ollama pull embeddinggemma
.venv/bin/python scripts/smoke_test_embeddings.py --model embeddinggemma
~~~

O script usa dois textos sintéticos, SQLite temporário e uma consulta idêntica a um dos trechos. Ele confirma que o endpoint responde, as dimensões são coerentes e a busca vetorial encontra o vetor esperado. Não lê nem envia documentos pessoais. Não é benchmark de qualidade, nem substitui testes com documentos reais. O nome do modelo é exemplo e pode ser trocado por outro modelo de embeddings compatível.


## Context Composer e validação

O Context Composer gera marcadores \`[E1]\`, \`[E2]\` etc., adiciona origem e localizador e preserva Evidence compatível com \`core.cognitive_task.Evidence\`. O orçamento é explicitamente em caracteres Unicode, não tokens. Trechos que não cabem são omitidos integralmente e seus IDs aparecem em skipped_chunk_ids; evidências não são truncadas silenciosamente.

EvidenceValidator confere se as citações remetem a chunks existentes e se hash, conteúdo e offsets coincidem com o índice. Seu factual_status continua \`not_independently_verified\`: integridade do link não demonstra entailment, ausência de contradição nem verdade factual da resposta.

## Ponte para o CognitiveTask

`KnowledgeRuntime` é a camada de ligação explícita entre recuperação e tarefa cognitiva:

- executa a recuperação com filtro de documento e orçamento de contexto;
- anexa os objetos `Evidence` resultantes ao `CognitiveTask`, evitando duplicar chunk_id já associado;
- registra no plano e no trace apenas contagens/localizadores técnicos, sem copiar o conteúdo sensível dos documentos para o log;
- prepara uma mensagem de contexto em papel `user`, delimitada como material documental não confiável e orienta o modelo a não obedecer instruções contidas nas fontes;
- expõe a validação estrutural das citações.

Esta ponte é testável e reutilizável, mas ainda não é chamada pelo `MainWindow`, `CognitiveTaskExecutor` nem pelo fluxo normal do Chat. A interface não ingere documentos nem injeta RAG automaticamente nesta branch.

## Limites desta entrega

- Nenhuma integração ao Cognitive Pipeline, CognitiveTask, prompt do Chat, ChatView ou Cognitive Inspector.
- Não há reranker concreto, OCR ou tratamento de PDF escaneado.
- O usuário deve instalar e selecionar um modelo de embeddings; a aplicação não baixa modelos automaticamente.
- A avaliação atual é automatizada por testes de contrato e integração simulada; ainda faltam benchmarks de qualidade em corpus representativo e validação no Arch com o Ollama real.
- Embeddings de texto não são equivalentes a um verificador factual: recuperação e integridade de citações não garantem que uma alegação seja suportada pela fonte.

## Próximas entregas da Fase 3

1. Escolha e benchmark de modelos locais de embeddings em hardware leve, intermediário e potente.
2. Reranker concreto, opcional e avaliado por qualidade/latência.
3. Política de deduplicação, busca híbrida, filtros e orçamento por tokenizer/backend.
4. Integração ao Cognitive Pipeline, CognitiveTask e Validation Layer.
5. UI de ingestão, gestão documental, fontes e citações.
6. Corpus de avaliação RAG com precision@k, recall@k, MRR, cobertura, fidelidade, conflitos e resistência a prompt injection.

Nenhuma dessas capacidades pendentes deve ser anunciada como concluída.
