# Arquitetura

## Objetivo

Coordenar ferramentas determinísticas, motores de inferência, recuperação de conhecimento e recursos computacionais. O LLM é um componente selecionável, não o executor universal.

## Pipeline

1. Input Processing — recebe e preserva texto/anexos.
2. Semantic Analysis — estima intenção, capacidades, dificuldade, incerteza, risco e urgência.
3. Deterministic Processing — cálculos, parsers, conversões e verificações.
4. Knowledge Retrieval — recupera documentos e evidências.
5. Context Composer — organiza contexto e proveniência.
6. Cognitive Planner — decompõe tarefas e dependências.
7. Adaptive Execution Engine — seleciona ferramenta, modelo, backend ou nó.
8. Validation — verifica resultados, evidências e restrições.
9. Synthesis — produz resposta quando geração linguística for necessária.
10. Memory and Trace — registra decisões, estado e métricas.

O fluxo é adaptativo: tarefas simples podem terminar em ferramentas determinísticas. A implementação inicial em core/cognitive_pipeline.py executa Input Processing, Semantic Analysis, Deterministic Processing e Cognitive Planning por meio do Orchestrator. O planejador escolhe entre deterministic_only e llm_assisted.

A análise atual é heurística e lexical. O vetor de capacidades tem 12 dimensões com âncoras completas de palavras e expressões, para evitar correspondências acidentais dentro de palavras maiores; não usa embeddings nem classificador treinado.

O renderizador do Chat converte um subconjunto seguro de LaTeX em HTML compatível com QTextDocument. Delimitadores display (`\\[...\\]`, `$...$`) ocupam blocos centralizados destacados; delimitadores inline ficam no fluxo do parágrafo. Comandos não conhecidos permanecem visíveis, e a recuperação de erros é restrita a padrões explicitamente testados. O parser não substitui um motor matemático completo.

O Cognitive Inspector é uma projeção somente de leitura do CognitiveTask. Exibe a entrada original/normalizada, intenção, indicadores heurísticos, afinidades, subtarefas, plano, modelo selecionado, resultado quando disponível e eventos do Execution Trace. O trace também recebe eventos de seleção de modelo e estado da geração Ollama (início, conclusão, falha ou cancelamento). O painel mostra apenas a última tarefa da sessão e não persiste histórico cognitivo após reiniciar.

O Task Decomposer reconhece listas numeradas ou marcadas e conectores sequenciais explícitos. Registra intenção, afinidades, ordem e dependências no subtask_plan. A interface orienta o único modelo selecionado a responder cada parte e sintetizar o conjunto. Não há execução paralela, agentes independentes ou seleção automática de modelos especialistas nesta etapa. Os valores entre 0 e 1 são afinidades indicativas, sem calibração probabilística. Os indicadores de dificuldade, incerteza, risco e urgência são independentes.

As ferramentas determinísticas iniciais são uma calculadora baseada em AST com lista de operações permitidas e um conversor explícito de unidades. O sistema não executa código arbitrário. Marcadores de risco impedem o atalho determinístico e encaminham a solicitação ao modelo para análise; isso não equivale a revisão especializada ou validação clínica, jurídica ou financeira.

## Serviços transversais

- Adaptive Resource Manager: memória, aceleradores, filas e concorrência.
- Model Manager: inventário, carregamento e descarga de modelos.
- Knowledge Manager: ingestão, indexação, recuperação e sincronização.
- Swarm Manager: coordenação de peers autorizados.
- Telemetry: latência, uso, falhas e qualidade.
- Storage: configurações, histórico e metadados.

## Capability Vectorizer

Taxonomia inicial de 12 dimensões: conversa geral, programação, matemática/lógica, ciências/conhecimento, RAG/memória, visão, escrita/criatividade, pesquisa externa, ferramentas, planejamento, verificação e interdisciplinaridade.

Âncoras lexicais são a primeira implementação disponível. Embeddings e classificação semântica treinada ou calibrada permanecem futuros. Scores são afinidades heurísticas, não probabilidades; dificuldade, risco, incerteza e urgência são avaliados separadamente.

## Engines e recursos

Todos os backends implementam um contrato comum. Ollama é o primeiro adaptador planejado; llama.cpp, BitNet e execução remota são extensões futuras. A escolha manual do usuário deve ser respeitada.

Estimativa simplificada:
`Tprevisto = Tfila + Tcarregamento + Ttransferência + Texecução`

O orçamento de memória considera pesos, cache KV, contexto, buffers e sobrecarga do runtime. Swap/SSD não é substituto prático de RAM/VRAM para inferência interativa.

## Knowledge / RAG

Preservar fonte, hash, data, página/localização e trecho. Combinar busca lexical e vetorial quando apropriado. Preservar negações, números, unidades, condições, exceções e referências ao compor contexto.

## Swarm

- Control Plane: descoberta, identidade, heartbeat e telemetria.
- Data Plane: tarefas, resultados, arquivos e sincronização autenticados/criptografados.
- Execution Plane: despacho, especialistas e Map-Reduce.

O primeiro caso de uso é distribuir subtarefas independentes. RPC e inferência por camadas ficam experimentais; rede não é memória compartilhada.

## Princípios

Local-first, contratos versionados, testes antes de declarar funcionalidades prontas, segurança por padrão e benchmarks reproduzíveis que meçam qualidade e custo — não apenas tokens/s.
