# Contratos de dados

## CognitiveTask

Envelope versionado que atravessa o pipeline. Implementação inicial: \`core/cognitive_task.py\`.

Campos conceituais: schema_version, task_id, original_text, normalized_text, intent, capabilities, difficulty, uncertainty, risk, urgency, evidence, deterministic_results, execution_plan, subtasks, token_budget, ram_budget_mb, deadline_ms, execution_trace, result e status.

Scores são indicadores, não probabilidades calibradas. Implementações devem documentar escala e política.

## Evidence

Cada evidência identifica origem e conteúdo, podendo conter localização (página, seção ou offset) e metadados. Não remover a relação entre resposta e fonte.

## ExecutionTrace

Eventos registram estágio, estado, horário UTC e detalhes não sensíveis. Evitar armazenar segredos e documentos completos em logs.

## Engine Adapter

Contrato de engine fornece identificação, health check, inventário de modelos, capacidades, geração/streaming padronizados e fechamento/liberação de recursos.

## Versionamento

Mudanças incompatíveis no formato serializado exigem incremento de versão e migração explícita. Componentes não devem depender de campos internos não documentados.
