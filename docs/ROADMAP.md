# Roadmap do AILocal Universal

As fases são entregas progressivas. Uma funcionalidade só é considerada concluída quando código, testes, documentação e validação no ambiente-alvo correspondem ao escopo declarado.

## Fase 0 — Fundação

- [x] Repositório, visão de produto e princípios local-first.
- [x] Estrutura Python modular e contratos iniciais.
- [x] Documentação de arquitetura, segurança e roadmap.

## Fase 1 — Aplicação desktop local

- [x] Interface PySide6 com Chat, Modelos e configurações.
- [x] Contrato Engine Adapter e registry.
- [x] Adaptador Ollama: health, inventário, capacidades via /api/show e streaming NDJSON.
- [x] Workers Qt, seleção manual/automática, histórico e configuração local.
- [x] Cancelamento cooperativo, timeouts e tratamento de erros.
- [x] Validação visual do Chat, inventário e geração real no Arch Linux.

## Fase 2 — Núcleo cognitivo e execução controlada

- [x] Input Processing, Semantic Analysis heurística e Capability Vectorizer lexical.
- [x] Task Decomposer, Cognitive Planner, Orchestrator e Execution Trace.
- [x] Ferramentas determinísticas iniciais: calculadora AST restrita e conversor de unidades.
- [x] Cognitive Inspector e Cognitive Task Executor sequencial em worker Qt.
- [x] Estados explícitos, ordenação topológica e bloqueio de dependências inválidas/cíclicas.
- [x] Validation Layer estrutural e replay determinístico de ferramentas.

**Limite:** saídas livres do LLM permanecem não verificadas factualmente; a Validation Layer não substitui prova formal ou verificação de domínio.

## Fase 3 — Conhecimento local e RAG verificável

- [x] Loaders explícitos para texto, Markdown, formatos técnicos e PDF opcional.
- [x] Proveniência por URI, SHA-256, página, seção e offsets Unicode.
- [x] Chunking determinístico e índice lexical SQLite FTS5.
- [x] Embeddings via Ollama, SQLite vetorial e recuperação híbrida por RRF.
- [x] Context Composer, validação estrutural de citações e KnowledgeRuntime.
- [x] Biblioteca local privada e aba Conhecimento com workers Qt.
- [x] Integração opt-in do RAG ao Chat, fontes na resposta e evidências no Cognitive Inspector.
- [x] EmbeddingGemma e Qwen3 Embedding testados no Arch.
- [x] Ruff e 155 testes Pytest; Chat com RAG ligado/desligado e Cognitive Inspector validados.
- [x] Microbenchmark sintético: ambos embeddings acertaram o documento esperado em primeiro lugar nas quatro consultas; baseline lexical não recuperou as formulações sem sobreposição lexical.

**Limites desta entrega:** reranker concreto, corpus representativo com julgamento humano, OCR, orçamento efetivo por tokenizer e verificação semântica independente permanecem futuros. O microbenchmark sintético não estabelece um vencedor entre os embeddings nem prevê qualidade em corpus real.

## Fase 4 — NeuralModel Hub e gerenciamento adaptativo

### 4.1 — Registro e descoberta (implementado nesta branch; validação pendente)

- [x] Contrato versionável de ficha de modelo, artefato/runtime, licença e requisitos.
- [x] Registro JSON local com escrita atômica, versão de esquema e permissões restritas no Linux.
- [x] Descoberta do inventário Ollama sem inferir metadados ausentes.
- [x] Preservação de metadados curados durante sincronização do runtime.
- [x] Interface inicial NeuralModel Hub integrada à aplicação.
- [ ] Validar a interface e a persistência no Arch Linux.

### 4.2 — Hardware Compatibility Engine (implementação inicial nesta branch)

- [x] Perfil de CPU, RAM, disco e GPUs Linux via sysfs DRM.
- [x] Leitura de VRAM total/usada/livre e driver quando expostos pelo kernel.
- [x] Estados compatível/incompatível/não avaliado baseados em requisitos verificados.
- [ ] Validar medições na RX 5700 XT e em ambiente sem GPU dedicada.
- [ ] Ampliar probes por plataforma/runtime; fabricante e driver não comprovam Vulkan/ROCm/CUDA.

### 4.3 — Catálogo remoto por categorias (implementado nesta branch; validação pendente)

- [x] Manifesto JSON versionado, remoto com fallback local empacotado.
- [x] Categorias, busca textual, fichas, variantes Ollama e fontes oficiais.
- [x] Limites de tamanho, validação de esquema, procedência e nomes de modelo.
- [x] Variantes com plataforma incompatível aparecem sem ação de instalação.
- [ ] Ampliar o catálogo e revisar periodicamente as fichas/licenças.

### 4.4 — Download, instalação e gerenciamento (implementação nesta branch; validação pendente)

- [x] Confirmação explícita com modelo/tag, tamanho publicado e situação da licença.
- [x] Pull pelo endpoint Ollama em worker Qt, progresso NDJSON e cancelamento cooperativo.
- [x] Verificação do evento final de sucesso do runtime.
- [x] Remoção por API com confirmação e atualização do inventário.
- [ ] Validar download, cancelamento, retomada e remoção no Arch Linux.
- [ ] Adicionar verificação pós-download de digest quando o runtime expuser uma fonte confiável.

### 4.5 — Adaptive Resource Manager e Adaptive Model Selector (implementação inicial)

- [x] Contratos para estimativas de pesos, cache KV, overhead de runtime, posicionamento sugerido e confiança.
- [x] Estimativa de pesos por parâmetros totais e bits médios da quantização; nunca converte tamanho do artefato em RAM/VRAM.
- [x] Coleta de parâmetros, arquitetura, quantização e contexto pela API Ollama `/api/show`.
- [x] Cálculo do cache KV/token apenas para arquiteturas densas suportadas e quando todos os campos necessários estão disponíveis; arquiteturas híbridas permanecem sem estimativa automática.
- [x] Reserva configurável por código para buffers/runtime e margem de memória livre; posicionamentos GPU, CPU, híbrido, não cabe e desconhecido.
- [x] Seletor explicável integrado ao modo Automático do Chat; preferência preservada quando viável, alternativas impossíveis descartadas e fallback explicitado quando faltam metadados.
- [x] Painel do NeuralModel Hub exibe a justificativa da última decisão automática.
- [x] Testes unitários para estimativas, limites de contexto, MoE (parâmetros totais), seleção, fallback e extração dos metadados Ollama.
- [ ] Validar a decisão e as estimativas no Arch com Qwen3 4B, Qwen3.5 e Qwen3-Coder-Next 80B; comparar com medições reais de RAM/VRAM e `ollama ps`.
- [ ] Persistir benchmarks controlados de qualidade, latência, RAM/VRAM, estabilidade e estado quente/frio.
- [ ] Adicionar orçamento de contexto configurável e recomendações por tarefa/capacidade com métricas de qualidade.
- [ ] Implementar telemetria contínua, leases, concorrência e políticas de carregamento/descarregamento.
- [x] Expor snapshot de residência Ollama via `/api/ps` no contrato Engine Adapter (`RunningModelSnapshot`), preservando digest, tamanho, VRAM, contexto e expiração reportados.
- [x] Reconciliar snapshots com artefatos instalados por referência exata + digest; estados ausente/divergente/ambíguo permanecem inconclusivos e não reduzem a estimativa.
- [x] Avaliar reutilização do runner residente quando digest e contexto coincidem, sem contabilizar pesos/KV/buffers já alocados novamente para uma solicitação serial.
- [x] Integrar snapshots `/api/ps` ao seletor do modo Automático; manter modo Manual inalterado, carimbar observações e rejeitar snapshots com mais de 30 s ou próximos da expiração.
- [ ] Integrar slots concorrentes reais, leases e unload confirmado; validar medições frias/quentes no Arch Linux.
- [ ] Validar seleção quente/fria no Arch Linux, comparando estimativas com RAM/VRAM observadas e confirmando o comportamento de unload/keep-alive.

**Limites desta iteração:** as estimativas são teóricas e de confiança média; overhead de runtime é uma reserva fixa, não uma medição. O posicionamento híbrido é recomendação, não controle de offload. Na ausência de metadados suficientes, o seletor mantém o fallback legado e informa que não verificou a memória. Nenhum modelo é carregado/descarregado automaticamente por esta entrega.

**Saída:** primeira seleção automática orientada por memória, com justificativa e fallback explícito, sem afirmar compatibilidade quando os dados são incompletos.

## Fase 4.6 — Gerenciamento de conversas e perfis de processamento (implementação inicial)

- [x] Adicionar exclusão individual de conversa pela lista lateral do Chat.
- [x] Solicitar confirmação explícita com o título da conversa; a exclusão usa o ID estável e persiste atomicamente.
- [x] Manter uma conversa ativa válida após excluir a conversa selecionada; criar uma conversa vazia quando a última for removida.
- [x] Adicionar Leve (33%), Médio (66%) e Ultra (95%) na tela Configurações, com persistência em `AppConfig` e padrão Médio para configurações antigas.
- [x] Aplicar o perfil ao orçamento aproximado de threads de CPU enviado ao Ollama via `num_thread`, inclusive na execução cognitiva em múltiplas etapas.
- [x] Manter a estimativa de RAM/VRAM separada do percentual de processamento; não prometer limitação exata de GPU.
- [ ] Validar interface, persistência, exclusão e os três perfis no Arch Linux.
- [ ] Medir CPU/RAM/VRAM, latência e responsividade para comparar os perfis no hardware real.
- [ ] Calibrar custo de inferência por modelo/backend e tornar o seletor consciente do perfil para filtrar candidatos acima do orçamento computacional medido.

**Limite desta implementação:** o Ollama recebe um limite aproximado de threads de CPU, aplicado pelo runner no carregamento do modelo. O percentual real de CPU não é garantido, e não existe aqui um limitador portátil de computação da GPU. A elegibilidade de modelos continua baseada em viabilidade de memória independente do perfil de CPU.

## Fase 5.0 — Neural Elastic Execution: simulador de cache MoE

- [x] Contrato JSONL de acesso a especialistas, com identidade, token, tamanho e ordem de acesso.
- [x] Simulador determinístico de cache em bytes, com LRU, LFU e política estatística explicável.
- [x] Belady MIN como referência offline somente quando os especialistas têm tamanho uniforme.
- [x] Gerador de traces sintéticos estacionários, uniformes e com mudanças de fase.
- [x] Métricas de hit/miss, bytes simulados por token, evictions, bypass e ocupação máxima.
- [x] CLI e testes automatizados para as políticas e os contratos.
- [ ] Coletar traces reais de roteamento por instrumentação de runtime; Ollama /api/chat não expõe IDs de especialistas.
- [ ] Calibrar latência/largura de banda do armazenamento e validar o simulador contra medições físicas.
- [ ] Comparar predição neural somente após construir um corpus de traces reais representativo.

**Limite:** a Fase 5.0 simula substituição de cache, não inferência completa. Bytes lidos são misses simulados, não I/O físico; traces sintéticos não demonstram aceleração, qualidade ou viabilidade em hardware de 4 GB. Consulte `docs/NEURAL_ELASTIC_EXECUTION.md`.

## NAPA — Neural Adaptive Plasticity Architecture

### NAPA 1.0 — Cognitive Area Registry & Classifier
- [x] Registro declarativo e extensível de áreas cognitivas.
- [x] Separação entre ferramentas determinísticas, capacidades cognitivas e especialistas neurais.
- [x] Classificação multilabel com afinidades heurísticas explicáveis.
- [x] Reuso do Semantic Analysis e do Capability Vectorizer, sem duplicar as 12 dimensões existentes.
- [x] Integração retrocompatível em CognitiveTask.cognitive_areas.
- [x] Testes de contratos, classificação multilabel, integração e compatibilidade.

**Limites:** NAPA 1.0 classifica capacidades, mas não executa roteamento, não mede custos, não carrega especialistas e não modifica pesos. Scores são afinidades lexicais, não probabilidades calibradas. Consulte `docs/NAPA.md`.

### NAPA 1.1–1.6 — evolução planejada
- [ ] NAPA 1.1 — Neural Cognitive Cost Predictor (RAM, VRAM, CPU, GPU, I/O, latência e energia).
- [ ] NAPA 1.2 — Adaptive Cognitive Routing com orçamento, dependências, fallback e validação.
- [ ] NAPA 1.3 — Neural Progressive Retrieval integrado ao Knowledge/RAG.
- [ ] NAPA 1.4 — Neural Plasticity Engine para aprender prioridades a partir de resultados avaliados.
- [ ] NAPA 1.5 — Adaptive Neural Reorganization com versionamento, avaliação e rollback.
- [ ] NAPA 1.6 — Continual Performance Learning com proteção contra regressões e esquecimento.

A NAPA coordena Cognitive Core, NeuralModel Hub, NeuralMap, Knowledge/RAG, Adaptive Resource Manager e Neural Elastic Execution. Ela não substitui esses subsistemas nem lhes concede autoridade de execução.

## NeSA — Neural Semantic Atlas

### NeSA 0.1 — Semantic Page Indexer
- [x] Gerar uma ficha por página não vazia durante a ingestão local.
- [x] Extrair resumo extrativo e determinístico, candidatos lexicais a conceitos e palavras-chave sem invocar um LLM.
- [x] Preservar hash do arquivo e da página, URI, título, número/índice da página, seções, offsets do resumo e método/versão do extrator.
- [x] Reservar campo de entidades com contrato de extrator opcional; sem extrator configurado, não inventar entidades.
- [x] Persistir fichas e índice FTS5 no mesmo SQLite e na mesma transação dos chunks; exclusão em cascata e atualização substitutiva.
- [x] Expor listagem e busca lexical de candidatos por página sem alterar a recuperação híbrida de chunks.
- [x] Testar persistência, proveniência, busca, reingestão, remoção e fallback quando embeddings falham.

**Limites:** o resumo é extrativo, os conceitos são candidatos lexicais e a busca do catálogo é FTS5/OR; esta versão não implementa embeddings de páginas, NER padrão, grafo semântico, relações factuais nem recuperação progressiva. Consulte `docs/NEURAL_SEMANTIC_ATLAS.md`.

### NeSA 0.2–0.5 — evolução planejada
- [ ] NeSA 0.2 — Semantic Association Graph com relações tipadas, confiança e proveniência.
- [ ] NeSA 0.3 — Semantic Intent Frames integrados à classificação contextual da NAPA.
- [ ] NeSA 0.4 — Hierarchical & Progressive Retrieval combinando sumários, FTS5, vetores e expansão por incerteza.
- [ ] NeSA 0.5 — Relevance Plasticity, atualizando prioridades de recuperação somente com resultados avaliados.

A NeSA organiza conhecimento e recupera evidências. A NAPA decide quando consultá-la; o RAG mantém a proveniência e a validação de evidências. O NeuralMap poderá visualizar os grafos, sem duplicar a propriedade dos dados do Atlas.

## K.IA — Artificial Brain

### K.IA 0.1 — Rust Cognitive Runtime
- [x] Crate Rust independente com contratos serializáveis e IDs tipados.
- [x] Adaptive Cognitive Network em memória com nós, relações tipadas e integridade de referências.
- [x] Planner seletivo por capacidade, intenção, contexto, disponibilidade de executor e orçamento.
- [x] Orçamento lógico para CPU, RAM, GPU, VRAM e NPU; perfis 33%, 66% e 95% aplicados somente ao teto lógico de CPU.
- [x] ComponentExecutor para integrar motores sem acoplar o core ao Ollama ou llama.cpp.
- [x] Execução sequencial, eventos de telemetria sem payload do usuário e relatório de falhas.
- [x] Plasticidade operacional inicial por feedback avaliado e referenciado.
- [x] Testes Rust e CI com fmt, clippy e cargo test.

**Limites:** sem adaptadores reais, persistência, Tokio, coleta física de hardware, concorrência/cancelamento, treinamento paramétrico ou plasticidade estrutural. Reserva de hardware é lógica, não quota real do kernel. Consulte docs/KIA_ARCHITECTURE.md.

### K.IA 0.2 — Runtime Host & Python Bridge
- [x] Binário local persistente com JSONL v1 e comandos health, replace_state, plan, record_feedback, inspect e shutdown.
- [x] Validação do grafo desserializado, snapshot, orçamento e executores declarados pelo lado Python.
- [x] Cliente Python com processo persistente, handshake, timeout, correlação de request_id e shutdown.
- [x] Conversores NAPA/NeuralModel Hub/HardwareProfile para os contratos Rust.
- [x] Custos/alvos desconhecidos permanecem inelegíveis; tamanho de artefato não vira estimativa de memória.
- [x] Testes do subprocesso JSONL Rust e da ponte Python.

### K.IA 0.3 — ACCA Vertical Flow
- [x] Adiar a execução determinística até o planner Rust quando o host estiver disponível.
- [x] Exportar as ativações NAPA e o inventário instalado do NeuralModel Hub para uma rede cognitiva.
- [x] Registrar ferramentas determinísticas Python com capacidades, custo estático limitado e executor real.
- [x] Selecionar um componente/modelo somente com adaptador registrado, estimativa de RAM e alvo de execução explícitos.
- [x] Encaminhar modelo selecionado pelo Rust ao Ollama existente; sem reimplementar inferência.
- [x] Reservar pico de recursos por dimensão para o fluxo sequencial; política paralela permanece separada.
- [x] Reproduzir resultados determinísticos pela Validation Layer antes de atualizar prioridades.
- [x] Preservar pesos/contadores das conexões compatíveis quando replace_state sincroniza o próximo turno.
- [x] Validar resposta de LLM como estruturalmente presente, mas factual não verificada; completude não é presumida sem requisitos.
- [x] Fallback para o pipeline anterior quando K.IA não está instalada ou não encontra plano executável.
- [ ] Integrar RAG/NeSA como provedores selecionáveis pelo plano Rust.
- [ ] Ampliar seleção para GPU/híbrido após telemetria real de placement do backend.
- [ ] Validar o fluxo no Arch Linux com Ollama e modelos instalados.

### K.IA 0.4 — Persistent Cognitive Memory & Semantic Integration
- [x] Evoluir o protocolo local para v2 com restore_learning e export_network.
- [x] Restaurar apenas a rede cognitiva validada antes do primeiro replace_state; sempre reconstruir hardware, budgets e executores.
- [x] Persistir snapshots e event log em SQLite com transação, SHA-256, esquema versionado e permissões privadas.
- [x] Limitar o histórico persistido de eventos e preservar somente contagens/IDs/feedback avaliado; sem prompts, respostas ou conteúdo documental.
- [x] Integrar Knowledge Library + NeSA como componente de memória selecionável pelo planner Rust somente quando o RAG estiver habilitado.
- [x] Usar fichas NeSA/FTS5 como candidatos de documentos, restringir a busca inicial de chunks e expandir globalmente quando a cobertura for insuficiente.
- [x] Manter chunks originais como evidências citáveis; fichas de página são pistas de navegação, não evidência factual substituta.
- [x] Registrar IDs e contagens de candidatos NeSA no trace cognitivo sem copiar resumos ou conteúdo documental.
- [x] Testar persistência/restauração, integridade de hash, permissões e seleção do provedor de memória.
- [ ] Validar no Arch Linux o reinício do host, recuperação da plasticidade, busca NeSA progressiva e RAG no Chat.

### K.IA 0.5–0.8 — evolução planejada
- [ ] K.IA 0.5 — Adaptadores reais adicionais (llama.cpp), filas limitadas, timeout por tarefa, cancelamento e leases.
- [ ] K.IA 0.6 — Semantic Engine com embeddings de capacidades, CSR top-k/ANN e expansão por incerteza.
- [ ] K.IA 0.7 — Relações tipadas do NeSA com proveniência, dependência de fontes e resolução explícita de contradições.
- [ ] K.IA 0.8 — Cognitive Termination Controller no executor multi-etapas e benchmark A/B/C da ACCA com qualidade equivalente.

### Neural Plasticity & Development
- [ ] Plasticity 0.2 — benchmark de rotas, shadow mode, A/B, limiares e rollback.
- [ ] Neural Specialist Development — gerar e avaliar ferramentas e especialistas candidatos.
- [ ] Parametric Plasticity — LoRA/adaptadores treinados offline e versionados.
- [ ] Structural Plasticity — experimentos isolados em arquiteturas abertas, com snapshots e regressão.
- [ ] Autonomous Neural Development — propostas de evolução supervisionadas e auditáveis.

## ACCA — Adaptive Cognitive Computation Architecture

- [x] Especificar relevância calibrável, roteamento constrained, evidência com dependência, completude obrigatória e valor marginal de continuação.
- [ ] Treinar/calibrar parâmetros de relevância em dataset de avaliação versionado.
- [ ] Implementar embeddings semânticos + índice ANN e CSR com medição de recall.
- [ ] Implementar relação evidencial que agrupe republicações e mantenha contradições explícitas.
- [ ] Integrar termination controller ao executor de tarefas multi-etapas.
- [ ] Executar benchmark A/B/C com qualidade equivalente e perfis warm/cold.

A especificação matemática, limitações e metodologia de benchmark estão em docs/ACCA_MATHEMATICAL_MODEL.md. Os parâmetros iniciais do router não são apresentados como calibrados e nenhuma meta de economia é considerada comprovada.

## Fase 6 — Agentes especialistas e autoengenharia

- [ ] System Analyst em modo somente leitura.
- [ ] Code Analyst para análise do repositório e dependências.
- [ ] Test Engineer para reproduzir falhas e executar testes autorizados.
- [ ] Security Auditor com escopo e ferramentas restritos.
- [ ] Implementer em branch/worktree isolado, diff revisável e testes.
- [ ] Validação independente e aprovação humana antes de qualquer merge.

**Saída:** agentes especializados que analisam e propõem mudanças sem modificar main autonomamente.

## Fase 7 — Rede cooperativa (Swarm P2P)

- [ ] Identidade, pareamento e autorização explícita de nós.
- [ ] Descoberta, heartbeat e telemetria.
- [ ] Control Plane separado do Data Plane.
- [ ] Transporte autenticado e criptografado, limites, timeout e cancelamento.
- [ ] Despacho de subtarefas independentes e Map-Reduce.
- [ ] Transferência de arquivos com hash, integridade, retomada e controle de acesso.
- [ ] Tolerância a falhas, nós offline e reconciliação de resultados.

## Fase 8 — Laboratório de desempenho e backends experimentais

- [ ] BitNet e modelos de baixa precisão.
- [ ] llama.cpp RPC e execução remota experimental.
- [ ] Speculative decoding.
- [ ] Inferência distribuída por camadas após benchmark de rede e memória.
- [ ] Comparação de qualidade, latência, throughput, consumo e estabilidade.

## Regras transversais

- Não confundir score heurístico com probabilidade.
- Não marcar saída de LLM como verificada sem evidência ou validador independente.
- Toda ferramenta precisa de contrato, limites e testes positivos/negativos.
- Toda tarefa distribuída exige autenticação, autorização, timeout, integridade e cancelamento.
- Benchmarks registram hardware, modelo, quantização, contexto e estado quente/frio.
- main só recebe uma fase depois de revisão, CI aprovado e validação de aceitação no ambiente-alvo.


## K.IA 0.5 — Execution Safety Core (incremento inicial)

Implementado na branch feature/kia-execution-safety-v0.5:
- controle compartilhável por tarefa com cancelamento e deadline absoluto;
- execução controlada em CognitiveRuntime, preservando o método sequencial anterior;
- ComponentExecutor mantém compatibilidade, com ponto de extensão cooperativo para adaptadores que implementem polling;
- ExecutionLeaseManager administra capacidade lógica multidimensional, limite de tarefas ativas e fila de espera limitada;
- leases RAII liberam reservas ao sair do escopo, inclusive em retorno por erro;
- interrupção, timeout e rejeição por admissão aparecem como estados distintos no relatório.

Próximo incremento de K.IA 0.5: conectar os controles ao ciclo de vida das tarefas da aplicação/host, adaptar o cancelamento aos workers Python e adicionar adaptador llama.cpp somente após definir e testar sua interface de runtime.
