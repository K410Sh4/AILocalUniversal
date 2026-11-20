# AILocal Universal

> **Plataforma cognitiva local, adaptativa e distribuída.**

O AILocal Universal coordena modelos de linguagem, ferramentas determinísticas, conhecimento local e recursos computacionais. Seu princípio central é usar o mecanismo mais adequado para cada parte da tarefa — não acionar um LLM para tudo.

**Estado:** Fase 1 em validação operacional; núcleo cognitivo inicial da Fase 2 implementado em branch de desenvolvimento.  
**Plataforma prioritária:** Linux / Arch Linux.  
**Interface:** Python + PySide6.  
**Backend inicial:** Ollama.

## Funcionalidades da Fase 1

- Interface desktop PySide6 com abas Chat e Modelos.
- Consulta de disponibilidade do servidor Ollama.
- Inventário de modelos instalados.
- Chat via API /api/chat com streaming NDJSON.
- Modo manual e modo automático de seleção, limitados a modelos com capacidade de chat verificada.
- Identificação de capacidades via API `/api/show`, distinguindo chat, embeddings, visão e tools.
- Modelo preferido para o modo automático.
- Renderização de respostas em Markdown (negrito, listas, links, tabelas e blocos de código).
- Renderização local de um subconjunto de LaTeX: integrais, frações, raízes, potências, índices, símbolos gregos, vetores e barras superiores.
- Equações em bloco (`\\[...\\]` ou `$...$`) são exibidas centralizadas em painéis destacados; expressões inline permanecem no fluxo do texto. O parser preserva comandos desconhecidos visíveis e só corrige três erros frequentes e inequívocos (`\\limn`, `\\barx`, `\\vecE`). Não é um motor LaTeX completo.
- A fonte das equações display usa unidade absoluta em pontos (`20pt`), enquanto o texto padrão da conversa passou para `11pt`; os blocos matemáticos usam uma única célula sem separadores vazios e margens suaves.
- Histórico de conversas em JSON local.
- Configurações persistentes de URL, keep-alive e system prompt.
- Cancelamento de geração por worker em thread separada.
- Tratamento de indisponibilidade, timeouts e erros do protocolo.

O modo automático da interface escolhe o modelo preferido quando ele possui capacidade de chat verificada ou, na ausência dele, o primeiro modelo de chat em ordem estável. Modelos exclusivamente de embeddings e modelos sem metadados de capacidade verificáveis não entram no seletor de conversas.

## Fase 2 — Núcleo cognitivo (implementação inicial)

O envio de mensagens passa por um pipeline local antes de decidir a execução:

- Input Processing: normalização Unicode e de espaços, preservando o texto original e limitando entradas excessivas.
- Semantic Analysis: classificação heurística de intenção e indicadores separados de dificuldade, incerteza, risco e urgência.
- Task Decomposer: reconhecimento de listas e sequências explícitas, com subtarefas, intenção, afinidades e dependências.
- Cognitive Inspector: painel da última tarefa da sessão, com análise, indicadores heurísticos, capacidades, plano, subtarefas, rota, modelo, resultado e Execution Trace.
- Capability Vectorizer: vetor lexical explicável de 12 dimensões, usando âncoras em português e inglês.
- Deterministic Processing: calculadora com AST restrita e conversões explícitas de unidades comuns; não executa código arbitrário.
- Cognitive Planner: encaminha operações suportadas e de baixo risco para ferramentas locais; as demais seguem para o modelo configurado.
- Orchestrator: executa estágios e registra trace de início, conclusão e falhas.

Os scores são afinidades heurísticas entre 0 e 1, não probabilidades calibradas. Não há embeddings semânticos, classificador treinado, decomposição semântica livre, execução paralela de subtarefas ou seleção automática de especialistas por domínio. A decomposição atual depende de estrutura explícita e todas as partes são respondidas por uma única geração. As conversões de dados usam fatores decimais (base 1000). O conjunto de ferramentas é intencionalmente pequeno e será ampliado com testes específicos.

## Arquitetura

~~~mermaid
flowchart TD
 A[Entrada do usuário] --> B[ChatView]
 B --> C[MainWindow]
 C --> D[Seleção de modelo]
 D --> E[OllamaChatWorker]
 E --> F[OllamaEngine]
 F --> G[Ollama API]
 G --> H[Tokens NDJSON]
 H --> E
 E --> B
 C --> I[ConversationStore]
 C --> J[ConfigurationStore]
 C --> K[ModelsView]
 K --> L[OllamaStatusWorker]
 L --> F
~~~

A arquitetura completa continua incluindo RAG, Context Composer, validação de evidências, Resource Manager e execução distribuída. Esses blocos permanecem em fases posteriores; a Fase 2 ativa apenas o pipeline local descrito acima.

## Estrutura

- app/: janela, views e diálogos PySide6, incluindo o Cognitive Inspector.
- core/: projeção somente de leitura dos dados cognitivos para inspeção.
- core/: CognitiveTask, Input Processing, Semantic Analysis, Task Decomposer, Capability Vectorizer, ferramentas determinísticas, Cognitive Planner, Orchestrator e traces.
- engines/: contratos e adaptadores de inferência.
- workers/: operações de rede fora da thread da UI.
- storage/: configurações e histórico local.
- pipeline/: futuras etapas cognitivas.
- knowledge/: futura ingestão e recuperação RAG.
- resources/: futuro gerenciamento de recursos.
- swarm/: futura comunicação cooperativa P2P.
- docs/: arquitetura, contratos, roadmap, segurança e status.

## Requisitos

- Python 3.11 ou superior.
- PySide6 6.7 ou superior.
- httpx 0.27 ou superior.
- Ollama instalado e executando localmente.
- Pelo menos um modelo de chat baixado no Ollama.

## Instalação no Linux / Arch Linux

Enquanto a Fase 1 estiver em revisão:

~~~bash
git clone https://github.com/K410Sh4/AILocalUniversal.git
cd AILocalUniversal
git checkout bootstrap/project-structure
./install.sh
~~~

Após a integração da PR, basta clonar a branch padrão. O instalador cria um ambiente virtual em .venv e instala as dependências. Não instala nem inicia o Ollama automaticamente.

Inicie o aplicativo:

~~~bash
.venv/bin/ailocal
~~~

Se necessário, em outro terminal, inicie o serviço Ollama conforme a instalação local e baixe um modelo:

~~~bash
ollama serve
ollama pull qwen2.5:7b
~~~

O modelo acima é apenas um exemplo; escolha um modelo compatível com a memória do seu computador.

## Utilização

1. Abra a aba **Chat**.
2. Clique em **Atualizar modelos** para consultar o Ollama.
3. Escolha **Automático** ou **Manual**.
4. No modo manual, selecione um modelo identificado como compatível com chat.
5. No modo automático, selecione um modelo de chat e clique em **Definir preferido** para gravar sua preferência. Modelos de embeddings aparecem na aba **Modelos**, mas não são oferecidos para conversação.
6. Envie uma mensagem. A resposta será transmitida em streaming.
7. Use **Cancelar** para interromper a geração.
8. Abra **Configurações** para alterar URL, keep-alive ou system prompt.
9. Abra a aba **Cognitivo** para inspecionar a última tarefa analisada nesta sessão. O painel não persiste tarefas após reiniciar o aplicativo.

## Dados locais

- Configuração: variável XDG_CONFIG_HOME, padrão em ~/.config/ailocal-universal/config.json.
- Conversas: variável XDG_DATA_HOME, padrão em ~/.local/share/ailocal-universal/conversations.json.

Os arquivos são escritos atomicamente e com permissões privadas no Linux. Faça backup se quiser preservar o histórico ao reinstalar.

## Testes e qualidade

~~~bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
~~~

A suíte cobre contratos, seleção, persistência, protocolo Ollama simulado, análise cognitiva, ferramentas determinísticas, rotas do planejador e projeção de dados do Cognitive Inspector. A apresentação visual do novo painel e o fluxo integrado ainda precisam ser validados no Arch Linux.

## Roadmap

| Fase | Entrega |
|---|---|
| 0 | Fundação, documentação e contratos |
| 1 | Aplicação desktop, Ollama, streaming, histórico e configurações |
| 2 | Núcleo cognitivo e ferramentas determinísticas |
| 3 | RAG, Context Composer e validação |
| 4 | Gerenciamento adaptativo de recursos |
| 5 | Rede cooperativa, segurança e Map-Reduce |
| 6 | Laboratório BitNet, RPC e otimizações multi-host |

## Segurança e privacidade

O processamento permanece local por padrão. Não exponha a API Ollama diretamente à internet sem controles adequados. A comunicação remota e a execução entre nós ainda não estão habilitadas nesta fase.

Consulte docs/SECURITY.md.

## Documentação adicional

- Arquitetura: docs/ARCHITECTURE.md
- Roadmap: docs/ROADMAP.md
- Estado da implementação: docs/IMPLEMENTATION_STATUS.md
- Contratos de dados: docs/DATA_CONTRACTS.md
- Contribuição: CONTRIBUTING.md

---

**AILocal Universal — inteligência local coordenada por software, ferramentas e recursos reais.**

- Blocos matemáticos display usam fundo ardósia suave, borda neutra e espaçamento vertical para integrar as equações ao balão da resposta sem perder destaque tipográfico.
