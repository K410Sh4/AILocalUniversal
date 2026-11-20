# Contratos de dados

## CognitiveTask

Envelope versionado que atravessa o pipeline. Implementação inicial: `core/cognitive_task.py`.

Campos conceituais: schema_version, task_id, original_text, normalized_text, intent, capabilities, difficulty, uncertainty, risk, urgency, evidence, deterministic_results, execution_plan, subtasks, token_budget, ram_budget_mb, deadline_ms, execution_trace, result e status.

Scores de capacidades são afinidades heurísticas entre 0 e 1 nesta implementação, calculadas por âncoras lexicais e expostas em todas as 12 dimensões. Não representam probabilidades nem qualidade real do modelo. Dificuldade, incerteza, risco e urgência também são indicadores heurísticos independentes.

execution_plan registra a rota selecionada (atualmente deterministic_only ou llm_assisted) e os componentes planejados. deterministic_results armazena a saída estruturada de ferramentas locais. O texto original permanece em original_text; normalized_text é usado para análise sem apagar a entrada original.

## Evidence

Cada evidência identifica origem e conteúdo, podendo conter localização (página, seção ou offset) e metadados. Não remover a relação entre resposta e fonte.

## ExecutionTrace

Eventos registram estágio, estado, horário UTC e detalhes não sensíveis. Evitar armazenar segredos e documentos completos em logs.

## Engine Adapter

Contrato de engine fornece identificação, health check, inventário de modelos, capacidades, geração/streaming padronizados e fechamento/liberação de recursos.

## Versionamento

Mudanças incompatíveis no formato serializado exigem incremento de versão e migração explícita. Componentes não devem depender de campos internos não documentados.
