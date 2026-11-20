# Contratos de dados

## CognitiveTask

Envelope versionado que atravessa o pipeline. Implementação: core/cognitive_task.py.

Campos principais: schema_version, task_id, original_text, normalized_text, intent, capabilities, indicadores heurísticos, evidence, deterministic_results, execution_plan, subtask_plan, execution_trace, result, validation_report e status.

O campo validation_report é opcional para compatibilidade com tarefas serializadas antes da Validation Layer. A ausência do campo equivale a validação ainda não executada; não deve ser interpretada como aprovação.

## Subtask

Cada item de subtask_plan pode conter:
- id, order, text, intent, capabilities, depends_on e strategy;
- status: pending, running, validating, completed, failed, blocked, cancelled ou skipped;
- execution_kind: deterministic_tool ou llm;
- result: conteúdo e metadados da execução;
- validation_status: passed, needs_review ou failed;
- verification_status: verified_deterministic ou not_independently_verified;
- validation_report: checks e issues da etapa.

O estado completed significa que a etapa produziu uma saída aceita estruturalmente. Não significa que todo o conteúdo está factualmente correto.

## ValidationReport

O relatório no nível de CognitiveTask.validation_report contém:
- status: passed, needs_review, failed, running ou cancelled;
- structural_status: passed, failed ou in_progress;
- factual_status: verified_deterministic, not_independently_verified, failed ou not_verified;
- checked_at: timestamp UTC;
- summary: contagem de verificações, falhas, avisos e subtarefas verificadas;
- checks: nome, status, mensagem e detalhes de cada verificação;
- issues: código, severidade, mensagem e, quando aplicável, ID da subtarefa.

Interpretação:
- passed: verificações implementadas passaram e não existem avisos de revisão.
- needs_review: integridade estrutural passou, mas conteúdo de LLM não tem verificação factual independente.
- failed: inconsistência estrutural/determinística bloqueia a aceitação.
- verified_deterministic: resultado reproduzido pela mesma ferramenta local, com comparação de identidade, saída, estado de sucesso/erro e valor.
- not_independently_verified: conteúdo de LLM não foi confrontado com fonte independente nem validador específico do domínio.

A Validation Layer não deve promover uma saída de LLM a verified sem evidência verificável ou um validador de domínio explicitamente registrado.

## Cognitive Inspector

O Inspector consome uma projeção somente de leitura do CognitiveTask. Exibe a última tarefa da sessão, sem persistir histórico de execuções. A projeção não altera os contratos.

## Evidence

Cada evidência identifica origem e conteúdo e pode conter localização (página, seção ou offset) e metadados. A relação entre afirmação e fonte deve ser preservada.

## ExecutionTrace

Eventos registram estágio, estado, horário UTC e detalhes não sensíveis. Não armazenar segredos, prompts completos ou documentos integrais no trace.

## Engine Adapter

O contrato de engine fornece identificação, health check, inventário de modelos, capacidades e geração/streaming padronizados.

## Versionamento

A adição opcional de validation_report mantém a leitura de payloads anteriores. Mudanças incompatíveis futuras exigem incremento de schema_version e migração explícita.


## Conhecimento local — contratos iniciais da Fase 3

### LoadedDocument

Representa um arquivo explicitamente selecionado para ingestão:
- source_uri, title, sha256, media_type, size_bytes, metadata;
- pages: sequência de DocumentPage; PDFs usam page_number 1-based;
- document_id é estável por source_uri; nova versão da mesma origem substitui o índice anterior.

### DocumentChunk

Trecho extraído com:
- chunk_id determinístico, document_id, source_uri e source_sha256;
- content e offsets start_offset/end_offset em code points Unicode do texto extraído da página;
- page_number opcional e section_path Markdown;
- media_type e metadados de chunking.

Offsets de PDF são relativos ao texto extraído daquela página, não a posições de bytes do arquivo original. Extração de texto não garante reconstrução da disposição visual do PDF.

### SearchHit e HybridRetriever

SearchHit associa um DocumentChunk a score, rank e retrieval_sources. Scores são sinais de ordenação, não probabilidades. A busca lexical usa SQLite FTS5. A busca vetorial e o reranker são protocolos opcionais; nenhum backend vetorial concreto integra esta entrega. Quando há múltiplos rankings, a fusão inicial utiliza Reciprocal Rank Fusion.

### ContextBundle e CitationRecord

ContextBundle contém texto de contexto, Evidence do contrato CognitiveTask, registros de citação e IDs de chunks que não couberam no orçamento. O limite inicial é medido em caracteres Unicode, não em tokens. Cada Evidence mantém citation_id, chunk_id, document_id, hash, offsets e localização na origem.

### Evidence validation

EvidenceValidator verifica se a citação aponta para o chunk indexado e se conteúdo, hash e offsets permanecem consistentes. O relatório mantém factual_status como not_independently_verified: a integridade da referência não prova que uma afirmação é consequência lógica ou factual da fonte.


## Embeddings e recuperação vetorial — Fase 3

### OllamaEmbeddingProvider

- model_name identifica explicitamente o modelo de embeddings; não se presume que o modelo de chat também gere embeddings.
- embed(texts) envia lotes ao endpoint Ollama `/api/embed` e retorna um vetor por texto na mesma ordem.
- batch_size, dimensions, max_input_chars e keep_alive são configuráveis.
- truncate é falso por padrão para evitar truncamento silencioso.
- Cada vetor deve ter dimensão consistente e componentes numéricos finitos; vetor vazio ou de norma zero é rejeitado.

### SQLiteVectorStore

- Chave lógica: chunk_id + model_name.
- Metadados: document_id, source_sha256 e dimensions.
- Vetores são normalizados e armazenados como float32.
- search calcula similaridade cosseno, permite filtro por documento e não trata score como probabilidade.
- replace_documents substitui vetores de todos os chunks dos documentos fornecidos para aquele modelo, removendo entradas obsoletas.

### SearchHit vetorial

O backend vetorial recupera o chunk correspondente no índice lexical e valida document_id e source_sha256 antes de devolver SearchHit. Uma entrada vetorial sem chunk correspondente ou com hash divergente é descartada.

A geração e recuperação vetorial estão implementadas em branch de desenvolvimento, mas ainda não integradas ao Cognitive Pipeline/Chat. A compatibilidade de um modelo de embeddings e a qualidade da recuperação precisam ser medidas no ambiente-alvo.


## KnowledgeRuntime — integração da Fase 3

- retrieve(query, max_chars, limit, document_ids) devolve ContextBundle.
- attach_to_task(task, bundle) anexa Evidence pela chave chunk_id, evitando duplicações na lista de evidências.
- execution_plan recebe etapa knowledge_retrieval com estratégia e contagens.
- execution_trace recebe estado e contagens, sem copiar o texto dos documentos.
- as_untrusted_message(bundle) devolve uma mensagem de usuário que delimita os trechos como dados não confiáveis, orientando a não seguir instruções incorporadas nos documentos.
- validate_answer(bundle, answer) delega ao EvidenceValidator; status factual continua not_independently_verified.

O runtime ainda não é chamado pelo MainWindow nem pelo CognitiveTaskExecutor. A integração de UI/execução depende de ativação explícita, orçamento efetivo de contexto e testes operacionais.


A busca FTS5 remove palavras funcionais comuns da consulta antes de combinar os termos remanescentes por AND. Palavras de negação, incluindo “não” e “sem”, são preservadas para não alterar o sentido da consulta.


## Registro de validação do provider Ollama

Execução real no Arch Linux em 2026-11-20: modelo `embeddinggemma`, 768 dimensões, dois chunks sintéticos, duas correspondências vetoriais e duas híbridas. Consulta idêntica ao primeiro chunk resultou em similaridade cosseno 1.0. O SQLite de teste era temporário e foi removido. Essa execução valida o protocolo e o caminho vetorial básico, não a relevância semântica em corpus documental representativo.


## KnowledgeLibrary e interface Conhecimento — Fase 3.3

### KnowledgeLibrary

- `data_directory`: diretório persistente da biblioteca local, padrão XDG `$XDG_DATA_HOME/ailocal-universal/knowledge`.
- `list_documents()`: retorna metadados documentais com contagem de chunks.
- `ingest_files(paths)`: ingere somente os caminhos explicitamente fornecidos; devolve resultado por arquivo, contagem lexical/vetorial e aviso de falha vetorial parcial.
- `delete_documents(document_ids)`: remove os registros do índice e os vetores; não altera o arquivo original.
- `reindex_vectors()`: recria os vetores para todos os chunks existentes usando o modelo de embeddings atual.
- `search(query)`: devolve ContextBundle; quando o backend vetorial falha, tenta busca lexical e registra `last_search_warning`.

### KnowledgeLibraryWorker

Operações suportadas: `list`, `ingest`, `delete`, `search` e `reindex`. O worker abre e fecha a biblioteca em sua própria thread e emite resultados serializáveis; não compartilha conexões SQLite com a interface.

### Configuração

`AppConfig.embedding_model` é opcional e independente de `preferred_model` e `manual_model`. Configurações legadas sem essa chave continuam válidas. A troca do modelo é persistida, mas exige reindexação explícita para preencher o novo espaço vetorial.
