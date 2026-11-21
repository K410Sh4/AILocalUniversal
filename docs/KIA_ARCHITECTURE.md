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
