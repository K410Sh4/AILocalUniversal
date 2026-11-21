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


## NAPA — coordenação cognitiva adaptativa

A Neural Adaptive Plasticity Architecture (NAPA) é a camada de coordenação acima do Cognitive Core e dos subsistemas especializados. O registro cognitivo classifica uma solicitação em múltiplas áreas sem pressupor uma IA independente por área.

Os tipos iniciais são:
- deterministic_tool: calculadoras, conversores, recuperação e operações locais com contratos;
- cognitive_capability: comunicação, raciocínio, criatividade, conhecimento e apresentação;
- neural_specialist: especialistas de programação ou percepção quando um modelo adequado estiver disponível.

NAPA 1.0 reutiliza Semantic Analysis e Capability Vectorizer, grava as ativações explicáveis em CognitiveTask.cognitive_areas e não seleciona ou executa modelos/ferramentas. O NeuralModel Hub descreve os modelos; o NeuralMap representa estruturas; o Adaptive Resource Manager avalia limites; Neural Elastic Execution pesquisa a execução de especialistas; o Neural Plasticity Engine futuro aprenderá prioridades sob avaliação e rollback.


## NeSA — Neural Semantic Atlas

O Neural Semantic Atlas (NeSA) organiza o conhecimento documental em fichas por página, associadas ao hash, URI, título, página, seções e offsets da origem. Na versão 0.1, o resumo é extrativo e determinístico; palavras-chave e candidatos a conceitos são lexicais. Entidades só são preenchidas por um extrator explicitamente configurado.

As fichas são persistidas na mesma base SQLite e transação dos documentos/chunks, com FTS5 próprio para localizar páginas. O catálogo complementa — não substitui — a recuperação lexical/vetorial híbrida de chunks. A NeSA 0.1 não implementa grafo semântico, embeddings de página, relações factuais ou navegação hierárquica.

A NAPA coordena quando consultar o Atlas; o NeuralModel Hub e o Adaptive Resource Manager continuam responsáveis pelos modelos e recursos; EvidenceValidator permanece responsável pela integridade das evidências recuperadas.


## K.BA — Núcleo operacional da Brain Artificial

O runtime próprio começa como crate Rust independente em kba/. Ele possui contratos serializáveis para capacidades, componentes, conexões, solicitações e feedback avaliado. A rede de capacidades é fonte de verdade para a seleção dentro do runtime; subsistemas existentes serão sincronizados por contratos versionados, em vez de serem reescritos imediatamente.

O planner escolhe provedores por capacidade, afinidade heurística de intenção/contexto, prioridade operacional e disponibilidade de executor. Um orçamento lógico impede que a soma dos custos estimados ultrapasse os limites configurados. A execução inicial é sequencial por ComponentExecutor, sem acoplamento ao motor de inferência.

O feedback só altera a prioridade de uma conexão quando contém uma referência de validação independente. Esta proteção não substitui a qualidade do avaliador: ela exige que a origem da avaliação seja rastreável. A telemetria registra IDs, estado e duração, mas não serializa o payload do usuário.

O snapshot de hardware é fornecido pela aplicação. O orçamento não impõe limites ao kernel nem garante percentuais de uso físico. Providers de hardware, controle real de processo, concorrência, cancelamento e adaptadores Ollama/llama.cpp são etapas posteriores.
