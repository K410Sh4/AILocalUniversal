# AILocal Universal

> **Plataforma cognitiva local, adaptativa e distribuída.**

O AILocal Universal coordena modelos de linguagem, ferramentas determinísticas, conhecimento local e recursos computacionais. Seu princípio central é usar o mecanismo mais adequado para cada parte da tarefa — não acionar um LLM para tudo.

**Estado:** Fase 1 em implementação.  
**Plataforma prioritária:** Linux / Arch Linux.  
**Interface:** Python + PySide6.  
**Backend inicial:** Ollama.

## Funcionalidades da Fase 1

- Interface desktop PySide6 com abas Chat e Modelos.
- Consulta de disponibilidade do servidor Ollama.
- Inventário de modelos instalados.
- Chat via API /api/chat com streaming NDJSON.
- Modo manual e modo automático de seleção.
- Modelo preferido para o modo automático.
- Histórico de conversas em JSON local.
- Configurações persistentes de URL, keep-alive e system prompt.
- Cancelamento de geração por worker em thread separada.
- Tratamento de indisponibilidade, timeouts e erros do protocolo.

O modo automático inicial escolhe o modelo preferido quando disponível ou, na ausência dele, o primeiro nome em ordem estável. Roteamento semântico por capacidades será implementado na Fase 2.

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

A arquitetura cognitiva-alvo inclui Input Processing, Semantic Analysis, processamento determinístico, RAG, Context Composer, Planner, Adaptive Execution, Validation e Synthesis. Esses componentes serão implementados nas fases subsequentes; sua descrição não significa que estejam todos ativos.

## Estrutura

- app/: janela, views e diálogos PySide6.
- core/: CognitiveTask, Orchestrator, Capability Vectorizer e traces.
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
4. No modo manual, selecione o modelo.
5. No modo automático, selecione um modelo e clique em **Definir preferido** para gravar sua preferência.
6. Envie uma mensagem. A resposta será transmitida em streaming.
7. Use **Cancelar** para interromper a geração.
8. Abra **Configurações** para alterar URL, keep-alive ou system prompt.

## Dados locais

- Configuração: variável XDG_CONFIG_HOME, padrão em ~/.config/ailocal-universal/config.json.
- Conversas: variável XDG_DATA_HOME, padrão em ~/.local/share/ailocal-universal/conversations.json.

Os arquivos são escritos atomicamente e com permissões privadas no Linux. Faça backup se quiser preservar o histórico ao reinstalar.

## Testes e qualidade

~~~bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
~~~

A suíte cobre contratos, seleção, persistência e protocolo Ollama usando transporte HTTP simulado. O uso com serviço Ollama real e o comportamento gráfico precisam de validação em máquina Linux.

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
