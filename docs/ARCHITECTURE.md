# Arquitetura

## Objetivo

Coordenar ferramentas determinísticas, motores de inferência, conhecimento local e recursos computacionais. O LLM é um componente selecionável, não o executor universal.

## Pipeline-alvo

1. Input Processing — recebe e preserva entrada/anexos.
2. Semantic Analysis — estima intenção, capacidades, dificuldade, incerteza, risco e urgência.
3. Deterministic Processing — cálculos, parsers, conversões e verificações locais.
4. Knowledge Retrieval — recupera documentos e evidências.
5. Context Composer — organiza contexto e proveniência.
6. Cognitive Planner — decompõe tarefas, dependências e orçamento.
7. Adaptive Execution Engine — seleciona ferramenta, modelo, backend ou nó.
8. Validation — verifica estrutura, dependências, ferramentas e evidências.
9. Synthesis — produz a resposta integrada quando geração linguística é necessária.
10. Memory and Trace — registra decisões, estado e métricas.

O fluxo é adaptativo: tarefas simples podem terminar em ferramentas determinísticas.

## Cognitive Task Executor

Pedidos com duas ou mais subtarefas explícitas são executados em série, fora da thread da interface. A ordem é topológica, dependências inválidas/cíclicas são rejeitadas, ferramentas locais são usadas quando intenção e risco permitem, as demais etapas usam o mesmo modelo selecionado e uma chamada final sintetiza os resultados.

Não há execução paralela, seleção multi-modelo autônoma ou agentes de autoengenharia nesta etapa.

## Validation Layer

Confere resultados não vazios, dependências, replay determinístico de ferramentas e completude. Resultados determinísticos são reproduzidos localmente quando a replay coincide. Saídas livres do LLM permanecem não verificadas factualmente.

## Conhecimento / RAG

A Fase 3 implementa loaders locais explícitos, proveniência por URI e SHA-256, chunking por página/seção, índice lexical SQLite FTS5, provider Ollama /api/embed, armazenamento vetorial SQLite e fusão RRF.

O Chat usa RAG somente quando o usuário ativa a opção. A validação confirma proveniência e integridade da referência, mas não prova a verdade nem o suporte lógico de alegações geradas pelo modelo.

## NeuralModel Hub e hardware

O NeuralModel Hub separa a ficha lógica do modelo dos artefatos associados a runtimes. A descoberta do Ollama registra somente fatos retornados pelo inventário local. Licença, publicador, parâmetros, arquitetura, quantização, contexto e requisitos permanecem desconhecidos quando não há fonte.

O registro é local, versionado, com escrita atômica e permissões restritas no Linux. Metadados curados não são apagados durante a sincronização do runtime. Arquivos de catálogo inválidos são preservados e não sobrescritos silenciosamente.

O HardwareProfiler coleta CPU, RAM, armazenamento e GPUs expostas pelo sysfs DRM do Linux. Fabricante e driver não são usados como prova de disponibilidade de CUDA, ROCm ou Vulkan.

O CompatibilityEngine retorna **compatível**, **incompatível** ou **não avaliado**. Ele só afirma compatibilidade quando limites mínimos de recursos estão verificados e vinculados a evidência. O tamanho do artefato em disco nunca substitui o consumo de inferência estimado ou medido.

## Swarm

- Control Plane: identidade, autorização, descoberta, heartbeat e telemetria.
- Data Plane: tarefas, resultados, arquivos e sincronização autenticados/criptografados.
- Execution Plane: despacho e Map-Reduce.

Descoberta de peer não concede autorização. O primeiro caso de uso divide subtarefas independentes. RPC e inferência por camadas permanecem experimentais.

## Princípios

Local-first, contratos versionados, segurança por padrão e benchmarks reproduzíveis que meçam qualidade e custo, não apenas tokens/s.
