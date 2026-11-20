# RAG local — especificação da primeira entrega

## Objetivo

Dar ao AILocal Universal uma base local e rastreável de ingestão e recuperação, antes de integrar a recuperação ao prompt do Chat. A implementação inicial está isolada na branch `feature/rag-v1`.

## Fluxo

~~~mermaid
flowchart TD
  A[Arquivo escolhido pelo usuário] --> B[Loader local]
  B --> C[SHA-256 + metadados]
  C --> D[Texto / páginas]
  D --> E[Chunker]
  E --> F[SQLite FTS5]
  F --> G[Retriever lexical]
  H[Backend vetorial futuro] -. opcional .-> I[RRF]
  G --> I
  I --> J[Context Composer]
  J --> K[Evidence + citações]
  K --> L[Evidence Validator]
~~~

## Ingestão suportada

- TXT e formatos técnicos declarados: UTF-8.
- Markdown: UTF-8, títulos e blocos preservados como limites de chunking.
- PDF: extração de texto selecionável por pypdf opcional. PDFs criptografados são rejeitados; OCR não existe nesta entrega.
- Limites padrão: 20 MiB por arquivo, 2 milhões de caracteres extraídos e 500 páginas por PDF. Os limites podem ser ajustados na construção do loader.
- Não existe varredura automática do disco, download de documentos ou execução de conteúdo.

## Proveniência

Cada documento registra URI local e SHA-256 dos bytes originais. Cada chunk mantém digest da origem, offsets Unicode do texto extraído, número de página quando aplicável e caminho de seção Markdown. Para PDFs, offsets são relativos ao texto extraído da página, não aos bytes nem à posição visual no PDF.

O identificador do documento é estável por URI. Reingestão do mesmo caminho substitui a versão indexada, evitando que conteúdo antigo permaneça nos resultados da mesma origem.

## Indexação e recuperação

SQLite FTS5 fornece busca lexical local e filtros por document_id. O tokenizador Unicode remove diacríticos para facilitar pesquisas em português. A consulta atual exige correspondência de todos os termos identificados.

HybridRetriever combina ranking lexical com ranking de um backend vetorial opcional usando Reciprocal Rank Fusion. Protocolos vetoriais e de reranking existem, mas nenhum backend/embedding concreto foi incluído nesta primeira entrega. Os scores são sinais de ordenação, não probabilidades.

## Context Composer e validação

O Context Composer gera marcadores `[E1]`, `[E2]` etc., adiciona origem e localizador e preserva Evidence compatível com `core.cognitive_task.Evidence`. O orçamento é explicitamente em caracteres Unicode. Trechos que não cabem são omitidos integralmente e seus IDs aparecem em skipped_chunk_ids; evidências não são truncadas silenciosamente.

EvidenceValidator confere se as citações remetem a chunks existentes e se hash, conteúdo e offsets coincidem com o índice. Seu factual_status continua `not_independently_verified`: integridade do link não demonstra entailment, ausência de contradição nem verdade factual da resposta.

## Próximas entregas da Fase 3

1. Provedor local de embeddings, inicialmente por uma capacidade de embeddings detectada no Ollama.
2. Índice vetorial substituível com persistência e filtros.
3. Reranker concreto, opcional e avaliado por qualidade/latência.
4. Integração ao Cognitive Pipeline, CognitiveTask e Validation Layer.
5. UI de ingestão, gestão, fontes e citações.
6. Corpus de avaliação com precision@k, recall@k, MRR, cobertura, fidelidade e testes de prompt injection.

Nenhuma dessas capacidades futuras deve ser anunciada como já implementada.
