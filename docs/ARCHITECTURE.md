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

O fluxo é adaptativo: tarefas simples podem terminar em ferramentas determinísticas.

## Serviços transversais

- Adaptive Resource Manager: memória, aceleradores, filas e concorrência.
- Model Manager: inventário, carregamento e descarga de modelos.
- Knowledge Manager: ingestão, indexação, recuperação e sincronização.
- Swarm Manager: coordenação de peers autorizados.
- Telemetry: latência, uso, falhas e qualidade.
- Storage: configurações, histórico e metadados.

## Capability Vectorizer

Taxonomia inicial de 12 dimensões: conversa geral, programação, matemática/lógica, ciências/conhecimento, RAG/memória, visão, escrita/criatividade, pesquisa externa, ferramentas, planejamento, verificação e interdisciplinaridade.

Embeddings e âncoras semânticas serão a primeira abordagem. Scores são indicadores que exigem calibração; dificuldade, risco, incerteza e urgência serão avaliados separadamente.

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
