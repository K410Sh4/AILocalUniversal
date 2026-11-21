# Estado da implementação

Este documento diferencia código integrado, cobertura automatizada e validação operacional.

## Estado atual

| Área | Implementado | Limite / próximo passo |
|---|---|---|
| Interface PySide6 | Chat, Modelos, configurações e Cognitive Inspector | Refinamentos conforme validação visual no Arch |
| Engine Adapter | Contrato e registry | Novos backends em fases futuras |
| Ollama | Health, inventário, capacidades, NDJSON, streaming e snapshot de modelos residentes via `/api/ps`; reconciliação de identidade por referência + digest | Integrar medição confiável de memória incremental ao seletor/estimador; validar telemetria fria/quente e erros de runtime |
| Storage | Histórico e configuração JSON, escrita atômica; exclusão de conversa por ID na Fase 4.6 | Avaliar migração para banco conforme escala |
| CognitiveTask | Contrato versionado, serialização e relatório de validação | Migrações formais quando houver mudança incompatível |
| Input Processing | Normalização e preservação do original | Suporte posterior a anexos |
| Semantic Analysis | Intenção e indicadores heurísticos | Embeddings, calibração e avaliação |
| Capability Vectorizer | 12 dimensões lexicais explicáveis | Embeddings e classificador calibrado |
| Task Decomposer | Listas e conectores sequenciais explícitos | Melhor decomposição de pedidos mistos e não estruturados |
| Deterministic Tools | Calculadora AST restrita e conversor de unidades | Ampliar catálogo sob testes específicos |
| Cognitive Task Executor | Execução sequencial em worker, dependências, ferramenta local, subtarefas LLM e síntese | Sem paralelismo ou roteamento multi-modelo |
| Validation Layer | Estrutura, dependências, replay determinístico, completude e relatório | Sem verificação factual geral de texto LLM |
| Cognitive Inspector | Mostra resultados, estados, trace e relatório de validação | Mostra apenas a última tarefa da sessão |
| RAG / Context Composer | Base lexical/vetorial, aba Conhecimento e integração opt-in ao Chat implementadas na `feature/rag-v1`; EmbeddingGemma e Qwen3 Embedding validados no Arch; CI atual: Ruff + 155 testes Pytest (Python 3.11) | Reranker concreto, benchmark representativo de corpus, OCR, orçamento por tokenizer e verificação factual/entailment permanecem fora desta entrega |
| NeuralModel Hub | Registro local, catálogo curado, fichas Ollama, busca/filtros, pull e remoção; merge do catálogo preserva arquitetura, contexto, cache KV e metadados reais descobertos pelo runtime | Catálogo inicial ainda pequeno; licença/proveniência por versão, compatibilidade medida e validação operacional no Arch pendentes |
| Adaptive Resource Manager | Estimador frio, snapshot `/api/ps` com timestamp local, reconciliação por digest, expiração/frescor e seletor Automático com reutilização residente confirmada | Slots concorrentes, leases, unload confirmado, medições frias/quentes e validação operacional no Arch pendentes |
| NeuralMap 1.0 | Editor visual na interface, grafo declarativo versionado, validação estática, runtime sequencial, revisão limitada, dry-run sem I/O, worker assíncrono cancelável, JSON e edição de grafo em pacote `.neuralinjector` | Sem execução paralela de nós, backend de imagem registrado, integração NeuralPlugin ou validação ponta a ponta no Arch |
| NeuralInjector / NIP 0.1.0 | Schema do manifesto e plugin, exemplos, leitura/escrita ZIP com SHA-256 e limites, edição de pipelines e perfis adaptativos | Não instala nem executa código de plugins; assinatura/autoria não é verificada; leitor carrega entradas em memória; NeuralPlugin Manager ainda não implementado |
| Neural Elastic Execution Simulator | Simulador offline de traces MoE com LRU, LFU, política estatística e Belady MIN (somente tamanhos uniformes); CLI e testes | Ainda sem traces reais de roteamento; sem modelagem de latência de SSD, prefetch ou integração com runtime |
| NAPA 1.0 | Registro e classificação multilabel; fronteira ACCA valida IDs, afinidades, sinais e correspondência entre áreas/ativações | Afinidades heurísticas; sem predictor de custos, plasticidade, busca progressiva ou reorganização |
| NeSA 0.1 | Catálogo persistente de páginas com resumo extrativo, candidatos lexicais, palavras-chave, referências e busca FTS5 de páginas; integrado à ingestão RAG | Sem sumário abstrativo, NER padrão, embeddings por página, grafo ou recuperação hierárquica; validar no Arch |
| K.IA 0.5 | Runtime Rust com planner seletivo, host JSONL v2, memória SQLite e leases RAII; fluxo ACCA agora recebe avaliação residente e envia custo incremental de RAM ao planner | Host/protocolo continuam síncronos; leases ainda não são compartilhados entre tarefas da aplicação nem protegem unload; cancelamento não interrompe adaptadores bloqueantes; sem quotas físicas ou validação operacional no Arch |
| Roteamento especialista | Planejado | Fase 5 |
| Swarm P2P | Planejado | Fase 6 |
| BitNet / RPC | Experimental futuro | Fase 7 |

## Fase 3 — escopo inicial em desenvolvimento

A branch `feature/rag-v1` contém uma primeira base executável de conhecimento local:
- loaders explícitos para TXT, Markdown e PDF; pypdf é opcional;
- proveniência por URI, SHA-256, página, seção e offsets;
- chunking determinístico com limites e sobreposição;
- índice lexical SQLite FTS5, com filtros e substituição de versões do mesmo arquivo;
- provedor de embeddings local via Ollama `/api/embed`, com batching e validação de dimensões;
- armazenamento vetorial SQLite com vetores float32 normalizados, busca cosseno e filtro por documento/modelo;
- indexador vetorial e backend de busca compatível com `HybridRetriever`, com checagem de hash no retorno;
- fusão RRF de rankings lexical/vetorial; reranker permanece apenas como contrato;
- KnowledgeRuntime para anexar Evidence ao CognitiveTask e preparar mensagem de contexto delimitada como dado documental não confiável;
- composição de contexto com citações estáveis e orçamento em caracteres;
- validação estrutural de vínculos, hashes e trechos citados;
- script de smoke test para `/api/embed` e recuperação vetorial no Ollama real com dados sintéticos e SQLite temporário;
- `KnowledgeLibrary` para persistência, ingestão, consulta, exclusão do índice e reindexação por modelo;
- aba PySide6 **Conhecimento**, com seleção de arquivos, listagem, remoção do índice e prévia de recuperação;
- workers Qt para operações da biblioteca sem bloquear a thread da interface;
- seleção persistente de modelo de embeddings separada do modelo de chat;
- bancos SQLite em diretório local privado, sem mover ou excluir arquivos originais;

Validação operacional no Arch Linux: o usuário confirmou ingestão e busca lexical na aba Conhecimento, detecção dos modelos de embedding e recuperação vetorial/híbrida real com EmbeddingGemma e Qwen3 Embedding usando um documento de teste. A dimensão observada foi 768 para EmbeddingGemma; a consulta vetorial encontrou um chunk enquanto a lexical retornou zero, comprovando a origem `vector`. Também foi executado o smoke test sintético anterior com dois chunks e SQLite temporário removido. A integração opt-in ao Chat foi implementada depois dessas verificações e aguarda validação operacional específica no Arch. Esses ensaios não são benchmark de qualidade em corpus representativo. O reranker concreto, OCR e verificação semântica independente continuam fora do escopo.

## Validation Layer: escopo atual

A camada atual executa verificações reproduzíveis:
- resultado não vazio e saída estruturalmente presente;
- dependências referenciadas e concluídas;
- replay local de calculadora/conversor;
- comparação de ferramenta, saída textual, estado de sucesso/erro e valor numérico;
- presença de resultados para todas as subtarefas e da síntese final.

Estados do relatório:
- passed: verificações executáveis passaram e não existem avisos de revisão;
- needs_review: estrutura passou, mas conteúdo gerado por LLM não foi verificado independentemente;
- failed: inconsistência estrutural/determinística bloqueia a aceitação;
- cancelled: execução interrompida antes da validação final.

verified_deterministic significa que a mesma ferramenta local reproduziu a operação e a saída; não é prova formal de todo o domínio matemático. not_independently_verified significa que o texto do LLM não foi confrontado com fontes externas ou um verificador de domínio.

## Limitações conhecidas

- Afinidades de capacidades e indicadores de dificuldade, incerteza, risco e urgência continuam heurísticos e não calibrados.
- A decomposição depende de listas e conectores explícitos; pedidos mistos podem carregar contexto redundante nas subtarefas.
- O executor é sequencial e usa o mesmo modelo em todas as subtarefas LLM e na síntese.
- A síntese final é produzida por LLM e permanece factualmente não verificada.
- A Validation Layer atual não prova teoremas, não verifica fatos gerais e não substitui validação de domínio.
- O conjunto de ferramentas determinísticas é pequeno e cobre somente expressões/unidades suportadas.
- O Cognitive Inspector mostra apenas a última tarefa da sessão; o relatório de validação não é persistido como histórico de execuções.
- A integração opt-in do KnowledgeRuntime ao Chat e a exibição de fontes/citações foram implementadas na `feature/rag-v1` e passaram no CI com 155 testes; aguardam validação operacional após pull no Arch. Reranker concreto, avaliação RAG em corpus representativo, OCR, verificação semântica independente, gerenciamento adaptativo de recursos, roteamento multi-modelo e Swarm ainda não foram implementados.
- O renderizador matemático cobre um subconjunto de LaTeX, não um motor TeX completo.
- O orçamento de tokens atual é indicativo e ainda não é aplicado como limite efetivo da engine.

## Validação operacional

O usuário já demonstrou no Arch Linux/KDE o Chat com Ollama/Qwen, o inventário de modelos, a decomposição de pedidos, a execução sequencial e a rota de calculadora local + explicação pelo modelo. A Validation Layer desta entrega ainda precisa ser exercitada no ambiente-alvo com:
1. cálculo determinístico direto;
2. pedido composto cálculo + explicação;
3. explicação científica com aviso de revisão factual;
4. falha/cancelamento durante execução.


## Registro de validação operacional — 2026-11-20

Resultado informado e executado pelo usuário no Arch Linux:
- Python: 3.14.
- Pytest: 132 testes aprovados.
- Modelo de embeddings: `embeddinggemma`.
- Dimensão retornada: 768.
- Chunks sintéticos indexados: 2.
- Resultados vetoriais: 2.
- Resultados híbridos: 2.
- Similaridade cosseno do primeiro resultado para a consulta idêntica: 1.0.
- Armazenamento: SQLite temporário removido ao final.
- Origem dos documentos: dados sintéticos; nenhum documento pessoal foi ingerido.

Esse resultado comprova conectividade e execução do caminho técnico básico no ambiente-alvo. Não é benchmark de precisão/recall, nem valida a qualidade de respostas RAG em documentos reais.

O aviso de depreciação do pytest-asyncio foi tratado pela configuração explícita `asyncio_default_fixture_loop_scope = "function"` em `pyproject.toml`.


## Fase 3.3 — Biblioteca documental e aba Conhecimento

Implementado na branch `feature/rag-v1`:
- Serviço `KnowledgeLibrary` em diretório XDG de dados, com bancos SQLite lexical e vetorial.
- Seleção explícita de TXT, Markdown, PDF e formatos técnicos suportados.
- Listagem de documentos e contagem de chunks.
- Exclusão da entrada documental e vetores do índice, sem apagar o arquivo original.
- Prévia de busca híbrida; se embeddings falharem durante a consulta, a biblioteca tenta busca lexical e informa o aviso.
- Modelo de embeddings escolhido separadamente, salvo na configuração.
- Reindexação explícita de documentos existentes ao trocar de modelo.
- Worker Qt para listagem, ingestão, remoção, busca e reindexação.
- Diretórios privados (0700) e arquivos SQLite privados (0600) no Linux.

Validação automatizada atual: Ruff aprovado e 155 testes Pytest aprovados no CI. A aba Conhecimento foi validada visualmente no Arch e o usuário executou ingestão, busca lexical e recuperação vetorial com dois modelos. A integração recente ao Chat já passou no CI e aguarda teste operacional dedicado no Arch.


 
## Integração RAG opt-in ao Chat — CI aprovado; validação operacional pendente

- Controle explícito "Usar conhecimento local" no Chat, persistido em configuração e desativado por padrão.
- Recuperação executada em worker Qt independente; falhas de recuperação não bloqueiam o Chat e seguem com fallback sem contexto documental.
- Contexto documental delimitado como dado não confiável e inserido antes da mensagem original do usuário.
- Evidências anexadas à CognitiveTask sem duplicar chunk_id; plano e trace registram a recuperação.
- A resposta recebe a lista de fontes recuperadas. Citações do modelo são verificadas quanto a identificadores conhecidos e integridade de proveniência.
- Cognitive Inspector exibe documento, localizador e origem lexical/vetorial das evidências.
- A validação de citações é estrutural: não certifica que as afirmações da resposta sejam semanticamente implicadas pelas fontes.

A integração aguarda CI e validação operacional no Arch. Não altera a main.


## Fase 4.3/4.4 — catálogo online e instalação (implementação em branch; smoke test ponta a ponta parcial aprovado)

- Catálogo JSON versionado remoto em GitHub Raw, com manifesto local empacotado como fallback.
- Fichas curadas por categorias, pesquisa textual, variantes/tag, quantização, tamanhos publicados e links oficiais.
- Licença fica explicitamente não verificada quando não há fonte confirmada.
- Variantes limitadas por plataforma; recursos com suporte macOS-only não podem ser baixados no Linux.
- Busca e parsing em worker Qt separado da interface.
- Instalação via API oficial Ollama `/api/pull`, stream NDJSON com progresso, cancelamento, timeout de leitura sem limite para downloads longos e validação do evento `success`.
- Remoção via `/api/delete`, com confirmação na UI e atualização do inventário após o runtime concluir.
- Referências são validadas como identificadores de modelo Ollama; URLs arbitrárias e caminhos não são aceitos.
- Testes unitários para manifesto, fallback remoto, filtragem por categoria, restrições de plataforma, pull, progresso, falhas e remoção.

O usuário validou no Arch Linux o pull/instalação de um modelo pelo Catálogo online e o uso posterior no Chat. Cancelamento, retomada e remoção ainda precisam de teste operacional no ambiente-alvo. Tamanho publicado de download não representa requisito de memória de inferência ou espaço no volume configurado no Ollama.


## Registro de validação operacional do NeuralModel Hub — 2026-11-21

Resultado informado pelo usuário no Arch Linux:
- Um modelo foi selecionado e instalado diretamente pela aba Catálogo online do NeuralModel Hub.
- Modelo/tag confirmado pela captura da interface: `qwen3.5:2b-q4_K_M`.
- Após a instalação, esse modelo foi utilizado para uma conversa real pela interface Chat do AILocal Universal.
- A barra de status da interface exibiu `138.15 tokens/s` ao concluir a resposta observada; esse valor é o indicador apresentado pelo aplicativo nessa execução, não um benchmark controlado ou comparativo.
- O teste comprova o caminho funcional catálogo → pull/instalação no Ollama → descoberta pelo inventário → seleção/uso no Chat.
- O prompt usado como smoke test foi uma pergunta técnica sobre como lidar com o gargalo de modelos de aproximadamente 35B em PCs modestos.
- A resposta gerada chegou ao usuário, mas não foi considerada validada em qualidade: continha recomendações repetidas e imprecisas sobre modificar dimensões de embedding, heads e layers de modelos pré-treinados, além de confusão entre famílias/tamanhos de parâmetros.

Este é um smoke test operacional ponta a ponta reportado pelo usuário, não um benchmark de qualidade, velocidade ou consumo. A captura identifica o modelo como `qwen3.5:2b-q4_K_M` e mostra `138.15 tokens/s` para a resposta observada; o tempo de download e o perfil de recursos não foram registrados. Testes de cancelamento, retomada e remoção continuam pendentes.

## Fase 4.5 — Adaptive Resource Manager e Adaptive Model Selector (implementação inicial)

Implementado na branch `feature/adaptive-resource-manager-v1`:
- Serviço `AdaptiveResourceManager` que obtém snapshot de hardware, estima um modelo do registro e seleciona modelos de chat para o modo Automático.
- `ResourceEstimator` estima memória dos pesos a partir de contagem total de parâmetros e bits médios da quantização. Parâmetros ativos de MoE não são usados para reduzir o cálculo dos pesos.
- Estimativa do cache KV por token a partir de metadados explícitos de arquitetura retornados pelo Ollama. Nesta iteração, a fórmula FP16 só é aplicada a arquiteturas densas suportadas e com número de camadas, cabeças KV, comprimento de chave e comprimento de valor disponíveis. Arquiteturas híbridas e metadados ausentes permanecem desconhecidos.
- Reserva padrão de 768 MiB para runtime e margem de 15% sobre a memória disponível. Essas duas constantes são premissas conservadoras do estimador, não medições.
- Posicionamento sugerido: GPU, CPU, híbrido, não cabe ou desconhecido. A sugestão híbrida não força offload; o Ollama continua decidindo a distribuição real.
- Seletor usa compatibilidade estimada, preferência do usuário e execução em GPU como critérios explicáveis. Se todos os candidatos têm metadados insuficientes, mantém o fallback de preferência/nome estável e avisa que não houve validação de memória.
- Modo Manual continua respeitando a seleção explícita do usuário. O Chat Automático passa pelo novo seletor e o NeuralModel Hub mostra a justificativa da última decisão.

### Limites e validação pendente
- Estimativa de pesos usa coeficientes médios por quantização e margem; não equivale ao tamanho exato do GGUF nem a uma medição de memória do processo.
- O cache KV só é calculado quando o Ollama expõe arquitetura densa e todos os metadados requeridos. Não há inferência por nome do modelo.
- Overhead, alocações temporárias, cache quantizado, concorrência, fragmentação e outros estados do backend podem alterar o uso real.
- O seletor considera contexto de 4.096 tokens como ponto inicial fixo na integração atual.
- Benchmark de qualidade/latência, telemetria contínua, leases, concorrência e carregamento/descarregamento automático ainda não foram implementados.
- A validação operacional com Qwen3 4B, Qwen3.5 e Qwen3-Coder-Next 80B ainda precisa comparar estimativa com `ollama ps`, RAM/VRAM observadas e estabilidade no Arch Linux.



## Fase 4.6 — conversas e orçamento de processamento

Implementação inicial na branch `feature/chat-management-resource-profiles-v1`:
- exclusão de conversa individual pela interface do Chat com confirmação e persistência atômica por ID;
- a conversa selecionada é substituída pela mais recente, ou uma nova conversa vazia é criada após excluir a última;
- Configurações oferece Leve (33%), Médio (66%) e Ultra (95%), persistidos em `AppConfig.resource_profile`;
- arquivos de configuração legados sem a nova chave usam Médio;
- Ollama recebe `num_thread` proporcional ao percentual configurado e à quantidade de núcleos lógicos;
- a execução cognitiva em múltiplas etapas usa o mesmo orçamento de threads.

Ainda exige validação manual no Arch Linux. O controle de threads é aproximado: não garante percentual exato de CPU e não limita diretamente a computação da GPU. A opção do runner pode exigir recarga do modelo já carregado. O seletor mantém estimativas independentes de RAM/VRAM e ainda não possui benchmark de custo computacional por modelo para prometer uma escolha ótima em cada perfil.


## Fase 5.0 — Neural Elastic Execution Simulator

Implementação inicial na branch `feature/neural-elastic-simulator-v1`:
- contrato versionado por estrutura para traces JSONL: token, ID do especialista, tamanho em bytes e ordem de acesso;
- cache limitado em bytes, com suporte a especialistas de tamanhos diferentes nas políticas online;
- baselines LRU, LFU e política estatística baseada em frequência exponencialmente decaída e recência;
- Belady MIN somente como oráculo offline para objetos de tamanho uniforme;
- traces sintéticos reproduzíveis (stationary, uniform e phased), CLI e saída JSON;
- métricas de hits, misses, bytes lidos simulados, bytes por token, evictions, bypass e ocupação.

**Limites:** ainda não há trace real de IDs de especialistas capturado do Qwen/Ollama. A API de chat não expõe decisões do roteador MoE. O simulador não mede SSD, não executa kernels, não modela prefetch nem prova ganho de tokens/s. A predição neural e a validação em máquinas de 4 GB permanecem futuras. Consulte `docs/NEURAL_ELASTIC_EXECUTION.md`.


## NAPA 1.0 — Cognitive Area Registry & Classifier

Implementado na branch `feature/napa-cognitive-area-registry-v1`:
- registro declarativo de 13 áreas cognitivas em três tipos: deterministic_tool, cognitive_capability e neural_specialist;
- classificador multilabel que permite ativar capacidades simultâneas;
- reuso do intent e das 12 dimensões existentes do Capability Vectorizer;
- sinais explicáveis por dimensão legada, intent e âncoras lexicais;
- integração à SemanticAnalysisStage e armazenamento em CognitiveTask.cognitive_areas;
- leitura retrocompatível de tarefas serializadas antes do campo NAPA;
- testes unitários específicos e documentação da arquitetura.

**Limites:** a classificação é lexical/heurística e seus scores são afinidades, não probabilidades. A presença de uma área não aciona ferramenta, modelo ou plugin. Ainda não há estimador de custo, roteamento adaptativo, busca progressiva, aprendizado de conexões, modificação de parâmetros ou prova de economia de recursos. Validação operacional no Arch Linux permanece pendente.


## NeSA 0.1 — Semantic Page Indexer

Implementado na branch `feature/nesa-semantic-page-indexer-v0.1`:
- cria fichas para páginas não vazias durante a ingestão por DocumentIngestor e KnowledgeLibrary;
- resume por seleção extrativa determinística de sentenças, sem chamada ao Ollama/LLM;
- armazena candidatos a conceitos por bigramas, palavras-chave, seções Markdown e proveniência por URI, hash documental, hash da página, página e offsets do resumo;
- campo de entidades usa um contrato opcional de extrator; fica vazio e explicitamente marcado como não configurado na implementação padrão;
- persiste fichas e FTS5 no mesmo banco e transação dos documentos/chunks;
- reingestão substitui as fichas anteriores e delete_document remove fichas e entradas FTS;
- oferece listagem e busca lexical do catálogo sem alterar o HybridRetriever de chunks.

**Limites:** isso é um catálogo compacto de páginas, não um grafo semântico ou busca vetorial de páginas. Os conceitos são candidatos lexicais, não ontologia validada; FTS5 não compreende sinônimos. Os resumos são extrativos, não paráfrases semanticamente abstrativas. NER, sumários gerativos, associações tipadas e recuperação progressiva ficam para etapas posteriores. A validação operacional no Arch Linux permanece pendente.


## K.IA 0.1 — Rust Cognitive Runtime

Implementado na branch feature/kia-rust-cognitive-runtime-v0.1:
- crate Rust independente kia-cognitive-runtime em kia/;
- contratos serializáveis e IDs tipados para capacidades e componentes; CognitiveRequest identifica schema_version;
- grafo versionado em memória com relações tipadas;
- planner que seleciona componentes por capacidade, intenção, contexto, executor habilitado e orçamento;
- componentes com custo estimado explicitamente disponível; custo desconhecido não é tratado como custo zero;
- reserva lógica de CPU/RAM/GPU/VRAM/NPU e perfis 33/66/95 para CPU;
- trait de adaptador ComponentExecutor e registry de executores;
- execução sequencial com relatório, falhas e trace sem payload de usuário;
- atualização da prioridade operacional somente via feedback avaliado com referência independente;
- CI Rust: fmt, clippy e cargo test.

**Limites:** nenhum provider Ollama/llama.cpp, persistência, coleta física de hardware, execução concorrente, cancelamento, treinamento paramétrico ou mudanças estruturais de modelos. A reserva é lógica, não quota efetiva do sistema operacional. Validação manual no Arch Linux permanece pendente.


## K.IA 0.2 — Runtime Host & Python Bridge

Implementado na branch `feature/kia-runtime-host-bridge-v0.2`:
- binário persistente `kia-runtime-host` com JSONL v1 e comandos health, replace_state, plan, record_feedback, inspect e shutdown;
- validação de estado desserializado, IDs do grafo, referências, alvos, budget e executores anunciados pela aplicação;
- planejamento Rust sem inferência falsa: o host recebe IDs de executores Python disponíveis, retorna o plano e deixa a aplicação executar;
- cliente Python thread-safe com processo persistente, handshake, timeout, correlação de respostas, tratamento de EOF e shutdown;
- conversores do registry NAPA e ModelRegistry para capacidades/componentes;
- artefatos instalados de modelos só entram como componentes; custo e alvo desconhecidos permanecem inelegíveis, sem estimar RAM/VRAM pelo tamanho do arquivo;
- conversor conservador de HardwareProfile para snapshot, sem presumir que uma GPU detectada tenha backend computacional disponível;
- testes de protocolo subprocesso Rust e testes unitários Python para bridge/adapters.

**Limite:** a ponte está disponível como pacote reutilizável, mas ainda não foi inserida no ciclo de vida do MainWindow/CognitiveTaskExecutor. O Python ainda executa os motores; Rust planeja. A próxima etapa integra o plano à execução cognitiva e instala adaptadores de inferência explícitos.


## K.IA 0.3 — ACCA Vertical Flow

Implementação em andamento na branch feature/kia-acca-vertical-flow-v0.3:
- Chat pode iniciar kia-runtime-host sob demanda; sem binário ou plano executável, usa o fluxo anterior como fallback.
- O pipeline realiza normalização, NAPA e decomposição sem pré-executar a ferramenta determinística.
- O coordenador constrói rede com áreas NAPA, modelos de chat instalados, ferramentas determinísticas e snapshot do Adaptive Resource Manager.
- Calculator/unit_converter só são candidatos para suas intenções próprias e quando o risco é baixo.
- Modelo Ollama só entra no novo roteamento quando o artefato está instalado, consta no inventário atual, possui adaptador registrado e o estimador demonstra placement integral em RAM; GPU/híbrido continua no seletor legado.
- Rust escolhe o modelo/componente. Python/OllamaEngine continua sendo o executor de inferência.
- Para plano sequencial, o budget reserva o pico por dimensão, não soma custos de componentes que não estão ativos ao mesmo tempo.
- Resultado determinístico é reproduzido pela ValidationLayer; somente status passed + verified_deterministic produz feedback success para a plasticidade operacional.
- replace_state preserva pesos/contadores de conexões compatíveis, evitando zerar o aprendizado entre mensagens do mesmo processo.
- Resposta LLM recebe validação estrutural e gate de completude para requisitos declarados; continua not_independently_verified.
- Testes cobrem NAPA → planner → calculadora Python → replay de validação → feedback e planejamento de modelo com custo explícito.

**Limites:** plasticidade operacional permanece em memória do processo, sem persistência após reinício. A reserva sequencial é lógica, não quota do kernel. O custo CPU usa teto de threads configurado, não FLOPs medidos. GPU/híbrido, RAG/NeSA como provedor de plano, ANN/CSR semântico, energia, terminação entre etapas, treinamento e LoRA ainda não estão integrados. CI não substitui validação real no Arch Linux.


## K.IA 0.4 — Persistent Cognitive Memory & Semantic Integration

Implementação em andamento na branch feature/kia-persistent-semantic-memory-v0.4:
- Protocolo JSONL v2 com comandos restore_learning e export_network. O host valida snapshots antes de aceitar plasticidade anterior.
- Cliente Python restaura a rede persistida antes do primeiro replace_state e grava um snapshot após sincronização e feedback.
- SQLite local com tabela de snapshots e event log limitado a 10.000 eventos; save usa BEGIN IMMEDIATE, atualização transacional e SHA-256 do JSON canônico. Notas livres do feedback são removidas antes de gravar; pesos, contadores e validation_ref permanecem.
- Diretórios próprios da K.IA recebem modo 0700; banco recebe modo 0600. O schema do banco é versionado por PRAGMA user_version.
- Snapshot guarda somente a AdaptiveCognitiveNetwork: capacidades, componentes, conexões, pesos e feedback avaliado. Hardware, budget e executores são sempre reconstruídos.
- Persistência rejeita chaves que indicariam prompt, input de usuário, conversa, mensagens ou conteúdo documental. Eventos armazenam apenas contagens e hash do snapshot.
- NeuralComponent de memória memory-knowledge-library passa pelo planner Rust quando knowledge_enabled estiver ativo; o plano requer retrieval + generation. Python executa a busca existente em worker Qt e o modelo continua no Ollama.
- KnowledgeLibrary usa fichas NeSA FTS5 como candidatos de documento e executa busca híbrida nos chunks; se o conjunto de candidatos não cobrir o limite de resultados, expande para a biblioteca inteira.
- O worker devolve apenas IDs/posições/scores das páginas candidatas; o Cognitive Inspector recebe contagens e IDs, enquanto trechos citáveis continuam sendo chunks originais.

**Limites:** snapshot local não é criptografado; permissões privadas e hash protegem acesso casual/integridade, não substituem criptografia em disco. Persistência é local e por namespace; não sincroniza entre dispositivos. O log mantém no máximo 10.000 eventos e a rede carrega até 4.096 feedbacks durante carry_learning_from. Fichas NeSA continuam sendo busca lexical FTS5, não embeddings semânticos, e seus scores não são probabilidades. O custo e a priorização do provedor Knowledge são valores iniciais explícitos, ainda não calibrados por benchmark. CI não substitui validação manual no Arch Linux.


## K.IA 0.5 — Execution Safety Core (incremento inicial)

Implementação proposta na branch feature/kia-execution-safety-v0.5:
- ExecutionControl compartilha um sinal atômico de cancelamento e deadline por tarefa.
- CognitiveRuntime.execute_with_control verifica o controle antes de despachar, durante a espera por recursos e depois do executor retornar.
- ComponentExecutor oferece execute_controlled como extensão compatível; adaptadores antigos continuam funcionando, mas não podem ser interrompidos enquanto bloqueados.
- ExecutionLeaseManager impõe limite de tarefas ativas, orçamento multidimensional em uso e número máximo de tarefas aguardando.
- ExecutionLease usa RAII para devolver os recursos lógicos no fim da execução.
- Relatório distingue completed, failed, cancelled, timed_out e admission_rejected.
- Testes Rust cobrem deadline, cancelamento cooperativo, limite de recursos, saturação da fila e liberação de leases.

**Limites desta iteração:** o RuntimeHost JSONL v2 continua síncrono e a ponte Python serializa chamadas; os novos controles estão disponíveis na API Rust embutível, mas ainda não comandam o ciclo de vida do MainWindow/Ollama. Cancelamento real exige que cada adaptador bloqueante implemente polling ou suporte nativo a abort. Nenhuma quota do kernel é aplicada. O adaptador llama.cpp não foi incluído nesta entrega.
