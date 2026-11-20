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
