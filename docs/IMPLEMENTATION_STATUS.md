# Estado da implementação

Este documento diferencia código integrado, cobertura automatizada e validação operacional.

## Estado atual

| Área | Implementado | Limite / próximo passo |
|---|---|---|
| Interface PySide6 | Chat, Modelos, configurações e Cognitive Inspector | Refinamentos conforme validação visual no Arch |
| Engine Adapter | Contrato e registry | Novos backends em fases futuras |
| Ollama | Health, inventário, capacidades, NDJSON e streaming | Expandir testes de integração e erros de runtime |
| Storage | Histórico e configuração JSON, escrita atômica | Avaliar migração para banco conforme escala |
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
| NeuralModel Hub | Registro local, perfil de hardware e compatibilidade conservadora; catálogo remoto curado por categorias com fallback local; fichas e variantes Ollama com fontes; busca/filtros; pull NDJSON com progresso/cancelamento e remoção com confirmação, na branch `feature/neural-model-hub-v1` | Catálogo inicial ainda pequeno; catálogo expandido, licença/proveniência por versão/artefato, compatibilidade medida por runtime/contexto, Adaptive Model Selector e validação de cancelamento/retomada/remoção no Arch pendentes; pull e uso no Chat já validados pelo usuário |
| Adaptive Resource Manager | Planejado | Fase 4 |
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

