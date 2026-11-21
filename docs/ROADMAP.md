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

## Fase 5 — Agentes especialistas e autoengenharia

- [ ] System Analyst em modo somente leitura.
- [ ] Code Analyst para análise do repositório e dependências.
- [ ] Test Engineer para reproduzir falhas e executar testes autorizados.
- [ ] Security Auditor com escopo e ferramentas restritos.
- [ ] Implementer em branch/worktree isolado, diff revisável e testes.
- [ ] Validação independente e aprovação humana antes de qualquer merge.

**Saída:** agentes especializados que analisam e propõem mudanças sem modificar main autonomamente.

## Fase 6 — Rede cooperativa (Swarm P2P)

- [ ] Identidade, pareamento e autorização explícita de nós.
- [ ] Descoberta, heartbeat e telemetria.
- [ ] Control Plane separado do Data Plane.
- [ ] Transporte autenticado e criptografado, limites, timeout e cancelamento.
- [ ] Despacho de subtarefas independentes e Map-Reduce.
- [ ] Transferência de arquivos com hash, integridade, retomada e controle de acesso.
- [ ] Tolerância a falhas, nós offline e reconciliação de resultados.

## Fase 7 — Laboratório de desempenho e backends experimentais

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
