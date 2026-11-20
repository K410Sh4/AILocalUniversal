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

O fluxo é adaptativo: tarefas simples podem terminar em ferramentas determinísticas. A implementação atual executa localmente Input Processing, Semantic Analysis, Task Decomposer, Deterministic Processing e Cognitive Planning pelo Orchestrator.

## Cognitive Task Executor

Pedidos com duas ou mais subtarefas explícitas são executados em série, fora da thread da interface. A ordem é topológica, dependências inválidas/cíclicas são rejeitadas, ferramentas locais são usadas quando intenção e risco permitem, as demais etapas usam o mesmo modelo selecionado e uma chamada final sintetiza os resultados.

Não há execução paralela, seleção de múltiplos modelos, agentes autônomos ou roteamento especialista. Resultados intermediários são fornecidos às dependências seguintes e registrados no Cognitive Inspector.

## Validation Layer

A Validation Layer é executada depois de cada subtarefa e antes da síntese final:
- confere resultado não vazio;
- verifica que dependências já possuem saídas concluídas;
- reproduz cálculos e conversões determinísticos;
- compara ferramenta, saída, estado de sucesso/erro e valor;
- verifica que todas as subtarefas e a síntese possuem resultados.

Resultados determinísticos são marcados como reproduzidos localmente quando a replay coincide. Saídas de LLM recebem aviso not_independently_verified: a camada atual confere estrutura e fluxo, mas não pode demonstrar a veracidade de explicações livres. Uma conclusão de execução não é equivalente a uma validação factual.

Divergências determinísticas e falhas estruturais bloqueiam a síntese. Resultados de LLM com estrutura aceitável podem seguir para síntese, mas o relatório final fica em needs_review.

## Semântica e capacidades

A análise atual é heurística e lexical. O vetor de capacidades possui 12 dimensões indicativas. Não usa embeddings nem classificador treinado/calibrado. Dificuldade, incerteza, risco e urgência também são indicadores heurísticos independentes.

## Cognitive Inspector

O Inspector é uma projeção somente de leitura do CognitiveTask. Exibe entrada original/normalizada, intenção, indicadores, afinidades, plano, subtarefas, execução, relatório de validação e Execution Trace. Mantém apenas a última tarefa da sessão.

## Ferramentas determinísticas

A calculadora usa AST com lista de operações permitidas e o conversor suporta unidades explicitamente cadastradas. Não há execução de código arbitrário. O replay de ferramenta valida que o resultado registrado corresponde à operação reproduzida, não que todo o domínio matemático tenha prova formal.

## Conhecimento / RAG

A primeira base executável está isolada na branch `feature/rag-v1`: loaders locais explícitos para TXT, Markdown e PDF opcional; extração com URI e SHA-256; chunking por página/seção com offsets; índice lexical SQLite FTS5; protocolo vetorial/reranker; fusão RRF; Context Composer e validador estrutural de citações.

O provedor de embeddings, índice vetorial concreto, reranker concreto e integração ao Chat/Cognitive Pipeline continuam pendentes. O orçamento atual do Context Composer é em caracteres, não tokens. A validação confirma proveniência e integridade da referência, mas não prova a verdade nem o suporte lógico de alegações geradas pelo modelo.

## Recursos e engines

Todos os backends implementam contrato comum. Ollama é o adaptador atual. Model Manager futuro controlará carregamento/descarregamento, estado quente/frio e leases. O Resource Manager considerará pesos, cache KV, contexto, buffers e sobrecarga do runtime; swap/SSD não substitui RAM/VRAM para inferência interativa.

## Swarm

- Control Plane: identidade, autorização, descoberta, heartbeat e telemetria.
- Data Plane: tarefas, resultados, arquivos e sincronização autenticados/criptografados.
- Execution Plane: despacho e Map-Reduce.

Descoberta de peer não concede autorização. O primeiro caso de uso deve ser dividir subtarefas independentes. RPC e inferência por camadas permanecem experimentais.

## Princípios

Local-first, contratos versionados, testes antes de declarar funcionalidades prontas, segurança por padrão e benchmarks reproduzíveis que meçam qualidade e custo — não apenas tokens/s.
