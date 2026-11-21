# K.IA — Artificial Brain

Especificação e implementação inicial: 0.1

## Visão

K.IA é a inteligência que o AILocal Universal pretende construir. Artificial Brain (BA) descreve o paradigma: uma arquitetura cognitiva composta por capacidades, modelos, ferramentas, memórias, especialistas e adaptadores coordenados por um runtime próprio, em vez de depender da identidade ou das capacidades de um único modelo.

O AILocal Universal permanece a plataforma de desenvolvimento, integração, interface, distribuição e gerenciamento. K.IA é o runtime/inteligência que evolui dentro dela.

## Princípios

1. Modelos existentes são infraestrutura neural inicial, não o cérebro inteiro.
2. Capacidades são a unidade de coordenação: podem ser providas por ferramentas, modelos, especialistas, adaptadores ou memória.
3. Intenção e contexto determinam quais capacidades são candidatas; o orçamento de hardware limita quais podem ser ativadas.
4. A seleção operacional é distinta de treinamento paramétrico e crescimento estrutural.
5. Plasticidade usa somente feedback avaliado, referenciado e auditável.
6. Modelos-base permanecem preservados; novas especializações são versionadas separadamente.
7. Telemetria registra decisões e recursos sem copiar prompts, conversas ou documentos.
8. Falhas devem produzir estado explícito e permitir fallback/rollback; nenhuma autoalteração recebe autoridade irrestrita.

## Arquitetura-alvo

- Rust Cognitive Runtime: ciclo de vida de tarefas, contratos, grafo de capacidades, seleção, orçamento, execução e telemetria.
- NAPA: identifica intenções e áreas cognitivas.
- Cognitive Core / Planner: decompõe, ordena e planeja trabalho.
- Predictive Preprocessing: antecipa contexto e recursos.
- NeSA: organiza páginas e mapas semânticos.
- Knowledge/RAG: recupera fontes e evidências.
- NeuralModel Hub: cataloga motores, modelos e artefatos.
- Adaptive Resource Manager: fornece snapshots e políticas de recursos.
- Neural Elastic Execution: gerencia cache e execução elástica de especialistas.
- NeDA / Neural Development: treina e valida adaptadores e especialistas.
- Validation & Learning Feedback: julga resultados e autoriza atualizações de plasticidade.
- NeuralMap: visualiza snapshots, sem ser fonte de verdade.
- NeuralPlugin / NeuralInjector: distribui capacidades e especializações.

## Rust Cognitive Runtime 0.1 — escopo implementado

A crate independente está em kia/ (kia-cognitive-runtime) e fornece:

- IDs tipados CapabilityId e ComponentId;
- contratos serializáveis para CognitiveCapability, NeuralComponent, CognitiveConnection, CognitiveRequest e CognitiveFeedback;
- grafo em memória com validação de referências e conexões tipadas;
- tipos de nós para capacidades/componentes e conexões Supports, Requires, DelegatesTo, Complements, FallbackTo e ProducesInputFor;
- registro de executores externos por componente via ComponentExecutor;
- planejamento seletivo por capacidade, intenção, tags de contexto, score heurístico, executor disponível e orçamento;
- orçamento lógico para CPU (millicores), RAM, GPU, VRAM e NPU;
- perfis Leve/Médio/Ultra aplicados ao teto lógico de CPU;
- execução sequencial dos componentes escolhidos e relatório com eventos, duração, estimativa de custo e falhas;
- feedback avaliado que atualiza o peso da conexão com uma média móvel exponencial controlada;
- versão do grafo para rastrear alterações.

## Limites explícitos da versão 0.1

- O grafo e a telemetria vivem em memória; persistência SQLite/event sourcing ainda não foi adicionada.
- O executor é síncrono/sequencial. Tokio, filas limitadas, paralelismo e cancelamento vêm após definir leases e concorrência.
- Não há adaptadores reais para Ollama/llama.cpp nesta primeira entrega; testes usam executores simulados. A camada de adaptadores será adicionada sem acoplar o core a um motor.
- O snapshot físico é fornecido pela aplicação. A crate não mede sysfs, NVML, ROCm, cgroups ou uso real do Ollama.
- Orçamento de recursos é reserva lógica; não é quota do kernel e não garante porcentagem exata de CPU/GPU.
- Somente relações Supports influenciam o ranking nesta etapa. Outras relações são contratos para evolução.
- Scores são heurísticas, não probabilidades ou garantia de qualidade.
- Componentes sem estimativa de custo disponível não são elegíveis para seleção.
- Não há treinamento online, modificação de pesos, LoRA ou alteração de topologia de modelos.
- O contrato de feedback exige referência independente, mas a validade dessa referência é responsabilidade do componente de validação que o fornece.

## Ciclo operacional 0.1

1. A aplicação converte solicitação em CognitiveRequest com intent, contexto e capacidades requeridas.
2. O runtime valida os contratos.
3. O planner lista provedores habilitados com executor registrado, alvo físico e estimativa de recursos disponíveis.
4. O planner pontua candidatos e reserva recursos estimados sem exceder o budget.
5. O runtime executa componentes sequencialmente através do trait ComponentExecutor.
6. O relatório contém outputs, falhas e eventos sem incluir o payload do usuário.
7. Um validador independente pode emitir CognitiveFeedback com referência; o grafo atualiza a prioridade da rota.

## Próximas etapas

### Rust Runtime 0.2
- persistir snapshots versionados do grafo e feedback;
- implementar event log, idempotência e recuperação após reinício;
- acrescentar cancelamento, timeout e filas limitadas;
- adicionar adaptador real local para Ollama e um contrato OpenAI-compatible/llama.cpp;
- coletar snapshot de hardware através de providers de plataforma, sem misturar a coleta com a política de seleção.

### Adaptive Cognitive Network 0.1
- importar NAPA/Model Hub/NeSA para os contratos do runtime;
- criar sincronizador de registry Python/Rust com schemas versionados;
- converter traces e resultados de validação em eventos sem incluir conteúdo sensível.

### Plasticity 0.2
- coletar conjuntos de avaliação independentes;
- shadow mode e comparação A/B de rotas;
- limiares mínimos de amostras, confiança e regressão;
- aprovação e rollback de mudanças de prioridade.

### Desenvolvimento neural
- treinamento offline de pequenos classificadores/roteadores;
- adaptadores LoRA e especialistas próprios com base imutável;
- experimentos estruturais somente em arquiteturas abertas e snapshots reproduzíveis;
- promoção mediante benchmarks de qualidade, latência, memória e estabilidade.

## Build e testes

Na raiz do repositório:

~~~bash
cd kia
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets
~~~

A CI roda estes três comandos separadamente dos testes Python.


## K.IA 0.2 — Runtime Host & Python Bridge

A crate agora gera o binário local `kia-runtime-host`. Ele mantém o grafo em memória e atende JSONL versionado pelo stdin/stdout. Comandos: health, replace_state, plan, record_feedback, inspect e shutdown.

O protocolo aceita IDs de executores declarados pela aplicação; isso não faz o Rust executar os modelos. O host escolhe componentes e devolve ExecutionPlan. Python continua responsável por executar a seleção através dos adapters existentes. A sincronização de estado valida referências, alvos, snapshots e orçamento antes de substituir o estado em memória.

O pacote `kia_bridge` fornece:
- `KiaRuntimeClient`: inicia o executável sem shell, valida o handshake, serializa chamadas com lock, correlaciona request_id, aplica timeout de leitura e encerra por shutdown;
- conversão das áreas NAPA para nós de capacidade;
- conversão de ModelRecord/artefatos instalados em componentes, sem inferir RAM/VRAM pelo tamanho do arquivo;
- custos e alvos explicitamente fornecidos; custo/alvo ausente torna o componente inelegível;
- conversão de HardwareProfile para ResourceSnapshot, mantendo CPU/GPU/NPU conservadores;
- criação de CognitiveRequest com as áreas efetivamente ativadas pela NAPA.

Consulte `docs/KIA_RUNTIME_HOST_PROTOCOL.md` para o schema JSONL.


## K.IA 0.3 — ACCA Vertical Flow

O fluxo de chat com o host disponível passa por:
1. InputProcessing e SemanticAnalysis (NAPA) sem pré-executar a ferramenta determinística;
2. decomposição de tarefa e exportação das ativações NAPA;
3. sincronização de modelos instalados, ferramentas Python e snapshot do Adaptive Resource Manager;
4. seleção Rust considerando capacidades obrigatórias, executor registrado, custo explícito, alvo e budget;
5. execução da ferramenta escolhida em Python ou encaminhamento do modelo selecionado ao OllamaEngine;
6. ValidationLayer e, somente para resultado determinístico reproduzido, feedback operacional.

O processo Rust é dono da decisão de roteamento. Os motores e ferramentas continuam adaptadores externos. O payload de entrada enviado ao comando plan contém somente task_id; conversa, prompt e conteúdo documental permanecem na camada Python/Ollama.

No modo sequencial, a reserva é o pico por dimensão. Não utilizar essa política para planos paralelos. O caminho novo de modelos aceita somente placement CPU com estimativa completa em RAM e endpoint local confirmado; GPU/híbrido usa o fallback do seletor anterior até o provider conhecer a colocação real do Ollama.

O host mantém pesos e contadores compatíveis quando recebe novo replace_state durante o mesmo processo. A 0.4 acrescenta restore_learning/export_network e snapshot SQLite para recuperar a plasticidade entre reinícios. O feedback só é enviado quando a ValidationLayer reproduz um resultado determinístico; saídas LLM não fortalecem rotas automaticamente.

A ValidationLayer separa presença, cobertura de requisitos estruturados, completude ponderada e estado factual. Sem requisitos estruturados, completude fica como not_assessed; conteúdo LLM permanece not_independently_verified. Consulte docs/ACCA_MATHEMATICAL_MODEL.md.


## K.IA 0.4 — Memória cognitiva persistente

O cliente Python coordena a recuperação entre processos sem transferir o controle de execução do app:
1. Na primeira sincronização da sessão, lê o snapshot da rede em SQLite e o envia ao host como restore_learning.
2. Rust valida IDs, referências, pesos, feedback e relações. O próximo replace_state aplica pesos e contadores somente às conexões tipadas ainda compatíveis.
3. O cliente solicita export_network e persiste a rede após replace_state e record_feedback.
4. HardwareSnapshot, ResourceBudget e available_executors nunca são recuperados do disco; são reconstruídos a cada inicialização.
5. A gravação de snapshot e do evento é transacional; o hash SHA-256 protege contra alteração silenciosa do payload. O host Rust continua sendo a autoridade de validação semântica do grafo.

O banco padrão é `$XDG_DATA_HOME/ailocal-universal/kia/cognitive-memory.sqlite3` (fallback em `~/.local/share`). O diretório da aplicação é 0700, o subdiretório Kia é 0700 e o arquivo SQLite é 0600. Não há criptografia implementada. O snapshot armazena somente a rede cognitiva e não deve receber prompts, conteúdo de chat ou documentos.

## Integração NeSA + Knowledge

Quando `AppConfig.knowledge_enabled` está ativo, a rede inclui o provedor `memory-knowledge-library` e a solicitação exige `retrieval` e `generation`. Rust decide se esse provedor participa do plano; a execução continua na camada Python via KnowledgeRetrievalWorker. As fichas de página NeSA reduzem o conjunto inicial de documentos candidatos. A recuperação lexical/vetorial continua operando sobre chunks originais, com expansão global quando o candidato inicial não preenche o limite. Somente esses chunks são anexados como Evidence e podem ser citados.

A camada de memória não absorve automaticamente o conteúdo documental ou mensagens de usuário como fatos paramétricos. Plasticidade operacional recebe somente feedback avaliado com referência independente.
