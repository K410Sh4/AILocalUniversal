# Neural Semantic Atlas (NeSA)

## Objetivo

NeSA é o subsistema de organização e navegação do conhecimento documental do AILocal Universal. Ele cria fichas compactas por página e preserva vínculos exatos às fontes. NAPA decide quando consultá-lo; Knowledge/RAG continua responsável pela recuperação de chunks, composição de contexto e validação de evidências.

## NeSA 0.1 — Semantic Page Indexer

A primeira versão:
- produz uma ficha para cada página extraída não vazia;
- seleciona sentenças do próprio texto para um resumo extrativo e determinístico;
- extrai palavras-chave e candidatos lexicais a conceitos (bigramas);
- preserva URI, hash documental, hash da página, índice/número de página, tamanho, seções e intervalos do resumo;
- oferece contrato opcional para um extrator de entidades injetável;
- persiste fichas e índice FTS5 no mesmo SQLite e na mesma transação de documentos/chunks;
- substitui fichas na reingestão e remove fichas na exclusão do documento;
- disponibiliza listagem e busca lexical de candidatos por página.

## Contrato e proveniência

`SemanticPageRecord` contém:
- `page_id`: SHA-256 determinístico derivado da identidade da origem, hash da versão e identificação da página;
- `document_id`, `source_uri`, `source_sha256`: origem documental;
- `page_index`: posição 0-based na sequência extraída;
- `page_number`: número fornecido pelo loader, quando disponível;
- `content_sha256`, `content_char_count`: hash e tamanho do texto extraído;
- `summary`, `summary_spans`: resumo extrativo e intervalos em code points Unicode relativos ao texto extraído da página;
- `keywords`, `concepts`, `entities`: saídas dos extratores identificados;
- `section_paths`: seções Markdown preservadas pelos chunks;
- `summary_method`, `concept_method`, `entity_method`: identificação explícita dos métodos;
- `metadata`: metadados de execução, incluindo quantidade de palavras e media type.

O hash da página identifica o texto extraído, não a posição visual/bytes no arquivo original. Para PDFs, número de página é 1-based quando fornecido pelo loader. Offsets referem-se ao texto extraído da página, não a bytes do PDF.

## Métodos da versão 0.1

### Resumo

O resumo usa frequência dos termos não funcionais para priorizar sentenças e preserva sua ordem original. O alvo padrão é 35 palavras, configurável entre 20 e 50. Se a página tiver menos conteúdo, o resumo pode ser menor. Não há geração abstrativa, paráfrase nem chamada ao LLM.

### Palavras-chave e conceitos

Palavras-chave são termos lexicais relevantes extraídos do título e do texto. Conceitos são candidatos de bigramas adjacentes não funcionais. Ambos são pistas de indexação, não uma ontologia, relação causal ou afirmação factual validada. A busca do catálogo usa FTS5 com correspondência OR para ampliar candidatos; não compreende sinônimos nem equivale a busca semântica vetorial.

### Entidades

O contrato aceita um `EntityExtractor` explícito. Sem um extrator configurado, `entities=[]` e `entity_method=not_configured`. A implementação não tenta adivinhar nomes próprios a partir de capitalização, evitando confundir início de frase, títulos e entidades.

## Persistência e integração

A tabela `semantic_pages` possui foreign key para `documents`; a tabela FTS5 `semantic_pages_fts` indexa título, resumo, conceitos, entidades, palavras-chave e seções. Ambas são atualizadas na mesma transação SQLite em que `documents` e `chunks` são gravados.

`DocumentIngestor` e `KnowledgeLibrary.ingest_files` geram as fichas por padrão. Reingestão substitui a versão documental e suas fichas; `delete_document` remove fichas e linhas FTS. A falha no provider de embeddings não remove o catálogo, pois os registros locais já estão no banco lexical.

APIs iniciais:
- `SQLiteKnowledgeIndex.list_semantic_pages(document_id=None)`
- `SQLiteKnowledgeIndex.get_semantic_page(page_id)`
- `SQLiteKnowledgeIndex.search_semantic_pages(query, limit=10, document_ids=None)`
- `KnowledgeLibrary.list_semantic_pages(document_id=None)`
- `KnowledgeLibrary.search_semantic_pages(query, limit=10, document_ids=None)`

`SemanticPageHit.score` é score de ordenação BM25/FTS5, não probabilidade de relevância.

## Limites deliberados

NeSA 0.1 não implementa:
- embeddings ou reranking de páginas;
- NER padrão, grafo de associação, relação tipada ou inferência factual;
- sumários abstrativos gerados por LLM;
- Semantic Intent Frames;
- navegação hierárquica/progressiva ou expansão por incerteza;
- plasticidade das prioridades de recuperação.

O RAG atual continua recuperando chunks lexical/vetorialmente e validando a integridade das citações. O catálogo de páginas não substitui a evidência original e não é inserido automaticamente no contexto do Chat.

## Próximas etapas

1. NeSA 0.2 — Semantic Association Graph com relações tipadas e proveniência.
2. NeSA 0.3 — Semantic Intent Frames integrados à NAPA.
3. NeSA 0.4 — Hierarchical & Progressive Retrieval combinando sumários, FTS5, vetores e expansão por incerteza.
4. NeSA 0.5 — Neural Relevance Plasticity, aprendendo prioridades com resultados avaliados e proteção contra conteúdo pouco frequente.

## Validação

Os testes cobrem sumarização extrativa, candidatos lexicais, contratos de entidade opcional, preservação de seções e hashes, busca/persistência FTS5, filtros, reingestão, exclusão, integração de ingestão e resiliência à falha de embeddings. A validação operacional no Arch Linux permanece separada da CI.
