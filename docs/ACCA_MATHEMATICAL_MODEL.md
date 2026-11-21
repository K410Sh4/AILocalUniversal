# ACCA — Adaptive Cognitive Computation Architecture

## Objetivo e limites

ACCA é a camada matemática e operacional da K.IA que decide **quais operações devem ser executadas, por quais componentes, sob qual orçamento, com quais verificações e quando encerrar**. Ela não substitui a atenção dos Transformers. O modelo de linguagem continua executando sua arquitetura neural quando selecionado; ACCA reduz chamadas desnecessárias e organiza o trabalho externo ao modelo.

As fórmulas abaixo definem contratos e hipóteses. Coeficientes só se tornam parâmetros calibrados depois de treinamento/validação em um conjunto de avaliação representativo. Nenhuma economia percentual é assumida sem benchmark.

## 1. Relevância de capacidades

Dado pedido (q) e capacidade candidata (c), construa um vetor de sinais:

[
x(q,c)=[s_{sem},s_{ent},s_{rel},s_{ctx},s_{intent}]
]

- (s_{sem}): similaridade semântica por cosseno, somente quando embeddings compatíveis já existem;
- (s_{ent}): correspondência de entidades tipadas;
- (s_{rel}): correspondência de relações sustentadas por proveniência;
- (s_{ctx}): compatibilidade com domínio, modalidade e contexto;
- (s_{intent}): sinal de intenção NAPA.

Um modelo logístico pode produzir um score de ordenação:

[
R(q,c)=sigma(w^	op x(q,c)+b), quad
sigma(z)=rac{1}{1+e^{-z}}
]

Os coeficientes (w,b) são parâmetros versionados e calibráveis. Treinamento futuro deve usar rótulos de relevância, divisão temporal/por usuário quando aplicável e métricas de calibração, além de precisão/recall. Scores não são probabilidades até essa calibração ser demonstrada.

**Implementação atual:** NAPA fornece áreas ativas, afinidades heurísticas e sinais explicáveis. O contrato `CognitiveRequest` recebe atualmente as áreas ativas como `required_capabilities`, mas não transporta os valores de `AreaActivation.affinity`. Portanto, a afinidade calculada pela NAPA ainda não participa diretamente do ranking Rust. O planner combina qualidade-base, prioridade da conexão, afinidade lexical derivada de `request.intent` e tags de contexto. As âncoras NAPA são copiadas para `intent_tags`, mas só influenciam esse score quando seus tokens também aparecem na intenção categórica recebida pelo Rust. Ainda não há encoder semântico ligado ao Cognitive Router, vetor de entidades ou parâmetros de relevância treinados.

## 2. Cognitive Sparse Routing (CSR)

CSR trabalha sobre o grafo cognitivo, não sobre tokens dentro de um Transformer.

1. Obter a união dos candidatos vindos de NAPA, NeSA/Knowledge, ferramentas registradas e especialistas instalados.
2. Filtrar candidatos por capacidades obrigatórias, compatibilidade, executor disponível e orçamento.
3. Ranquear candidatos elegíveis com o modelo de relevância.
4. Selecionar o menor conjunto que cobre os requisitos e dependências.
5. Expandir a busca quando um requisito ficar sem provedor, a evidência for fraca ou a incerteza exceder o limite.

Uma busca exaustiva em (N) vetores de dimensão (d) custa (O(Nd)); índice ANN pode reduzir o custo médio, com compromisso explícito de recall. O grafo limita o trabalho ao subgrafo visitado. Não devemos fazer hard gate a uma única área lexical inicial: recall e cobertura de requisitos são medidos.

**Implementação atual e limite importante:** NAPA fornece 13 áreas; Rust percorre as capacidades ativadas e seus componentes associados. O planner atual é uma cobertura gulosa por capacidade: para cada `required_capability`, ordena provedores elegíveis e escolhe o primeiro que cabe no orçamento e possui executor/alvo disponíveis. Ele não calcula ainda a cobertura global mínima nem expande dependências transitivas. Embora o grafo valide relações `Requires`, `DelegatesTo`, `Complements`, `FallbackTo` e `ProducesInputFor`, somente `Supports` influencia a seleção. Essas relações não devem ser interpretadas como roteamento operacional nesta versão. Ainda não há busca ANN de capacidades nem expansão semântica por embeddings.

## 3. Seleção constrained e custo

Para um único provedor:

[
a^*=argmax_{ain A(q)}
left[
widehat Q(a)
-lambda_twidetilde T(a)
-lambda_ewidetilde E(a)
-lambda_rwidetilde R(a)
ight]
]

Sujeito a:
- cobertura das capacidades obrigatórias;
- executor/adaptador realmente registrado;
- (M(a)leq M_{disp}), VRAM e outros limites aplicáveis;
- alvo de execução suportado pelo backend;
- risco abaixo da política da operação.

Para uma sequência (pi), a função objetivo considera a qualidade do resultado final, dependências, repetição de contexto, tempo e recursos simultâneos. Em execução sequencial, o pico por dimensão é:

[
M_{pico,j}=max_{ainpi} M_j(a)
]

Em execução paralela, reservas simultâneas precisam ser somadas ou controladas por leases; a regra de máximo não pode ser reutilizada para tarefas concorrentes.

**Implementação atual:** o planner Rust faz seleção por cobertura e budget. A versão vertical 0.3 reserva o pico por dimensão porque a execução atual é sequencial. O modelo é considerado elegível no novo caminho somente quando o estimador coloca o artefato integralmente em RAM e o runtime local está registrado. GPU/híbrido permanecem no seletor legado até haver prova do placement real do Ollama.

## 4. Evidências e independência

Não usar (1-prod_i(1-s_i)) como confiança factual geral. Essa expressão pressupõe independência e pode contar cópias de uma mesma fonte como confirmações distintas.

Cada evidência deve registrar:
- documento/origem e linhagem de republicação;
- afirmação e trecho exato;
- apoio, contradição ou neutralidade;
- data e localização;
- confiabilidade da fonte com base em avaliação;
- grupo de dependência entre fontes.

Atualização bayesiana só é apropriada quando priors, likelihoods e dependências forem modelados e calibrados. Caso contrário, manter estados explícitos de suporte/contradição e exigir revisão. Integridade de citação prova que o trecho veio da fonte; não prova que a conclusão decorre dele.

## 5. Completude

Com pesos positivos (w_i) e cobertura (c_iin[0,1]):

[
C=rac{sum_i w_i c_i}{sum_i w_i}
]

A tarefa só passa quando (Cgeq	heta) **e** todos os requisitos obrigatórios estão completos:

[
orall iin R_{obrigatórios},quad c_i=1
]

Requisito ausente, resultado vazio ou status não concluído conta como incompleto. Quando o pedido não possui requisitos estruturados, a completude deve ficar como not_assessed; não presumir 100%.

**Implementação atual:** ValidationLayer.validate_chat_response calcula completude ponderada de subtarefas declaradas, aplica o gate obrigatório e sempre mantém saída de LLM como not_independently_verified.

## 6. Terminação

Para uma possível próxima operação:

[
Delta V =
mathbb E[Delta Q]
-lambda_tDelta T
-lambda_eDelta E
-lambda_rDelta R
]

Continuar quando houver requisito obrigatório pendente e uma ação válida dentro do orçamento, ou quando (Delta V>epsilon). Encerrar quando os requisitos forem atendidos e não houver ganho marginal justificável; parar também em limite de orçamento, risco ou cancelamento. Todas as parcelas precisam ser normalizadas para escalas comparáveis e suas estimativas precisam ser observáveis.

**Implementação atual:** o fluxo de chat é uma operação por turno; o controlador de terminação entre etapas ainda não está integrado ao CognitiveTaskExecutor. Latência é observada pelo worker e métricas Ollama quando disponíveis; energia ainda não é medida.

## 7. Comparação com Transformers e benchmarks

Para prefill denso, a atenção padrão tem custo (O(T^2d)); com KV cache, a atenção de um novo token ainda percorre aproximadamente (O(Td)) por camada e o cache cresce com o contexto. FlashAttention, GQA/MQA e PagedAttention mudam execução, memória ou representação do cache; CSR não substitui essas otimizações.

Medir três configurações com as mesmas tarefas, hardware, pesos, quantização, contexto e qualidade-alvo:

| Grupo | Configuração |
|---|---|
| A | LLM e backend otimizados, sem ACCA |
| B | LLM + componentes BA, sem CSR |
| C | LLM + ACCA + CSR + ferramentas determinísticas |

Registrar pelo menos chamadas ao LLM, tokens de entrada/saída, prefill, tokens/s, latência total, CPU, GPU, RAM, VRAM, energia (quando medida), completude, qualidade e taxa de falhas. Comparar warm/cold e reportar mediana/p95. Economia:

[
S=1-rac{C_{ACCA}}{C_{baseline}}
]

(C) deve ser a mesma métrica nas duas configurações. Não converter economia na operação isolada em economia total de conversa. Não afirmar vantagem sem equivalência de qualidade e intervalos de incerteza.

## 8. Escopo da K.IA 0.3

O primeiro fluxo vertical implementa NAPA → plano Rust → ferramenta determinística Python ou modelo Ollama selecionado → Validation Layer → feedback operacional somente para resultado determinístico reproduzido. O feedback permanece no host durante sua vida e é preservado em sincronizações de estado compatíveis.

Ainda não implementa encoder semântico próprio, ANN/CSR em escala, relações factuais do Atlas, energia, terminação entre subtarefas, treinamento de parâmetros ou LoRA. A migração Rust continua seletiva: Python mantém os adaptadores existentes e a inferência é executada pelo Ollama.
