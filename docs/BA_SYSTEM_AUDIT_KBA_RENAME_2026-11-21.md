# Auditoria técnica da Brain Artificial (BA) e migração para K.BA

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

**Data:** 2026-11-21  
**Base auditada:** `integration/unified-architecture-v1`, commit anterior à migração `cc9690659e40d252c8e52819a981bb25f8b8531d`  
**Escopo:** README, arquitetura, roadmap, status de implementação, ACCA, NAPA, NeuralDNA, runtime Rust, host JSONL, ponte Python, memória SQLite, testes e CI.  
**Tipo:** auditoria estrutural e de contratos; não equivale a revisão linha a linha de todos os arquivos ou a teste no hardware local.

## 1. Decisão de nomenclatura e fronteiras

A denominação **K.IA** foi substituída por **K.BA** no ramo integrado. A mudança inclui o crate Rust, binário host, pacote Python, imports, testes, documentação, configuração de empacotamento e workflow de CI.

- **Brain Artificial (BA):** sistema artificial adaptativo e desenvolvimental. Não é uma IA convencional, não é um LLM e não depende da identidade de um modelo externo.
- **K.BA:** núcleo operacional que fornece runtime, planejamento, coordenação, persistência e controle de recursos para a BA.
- **Modelos externos de IA:** provedores opcionais de capacidades especializadas. São componentes utilizáveis pelo ecossistema, não a BA.
- **AILocal Universal:** plataforma que desenvolve, integra, apresenta e distribui o ecossistema.

A distinção é obrigatória em novos documentos, código e benchmarks. O runtime operacional atual não deve ser apresentado como se já fosse a BA completa.

## 2. Estado real do K.BA atual

O núcleo Rust atual possui:
- contratos tipados para capacidades, componentes, conexões, solicitações e feedback;
- grafo de capacidades/componentes e conexões tipadas;
- planner que combina afinidade de intenção/contexto, qualidade-base, peso da conexão, executor disponível e orçamento;
- executor registry e interface de adaptadores;
- snapshots de recursos e reservas lógicas;
- cancelamento cooperativo, deadlines e leases RAII;
- host local JSONL v2 com limite de solicitação;
- memória operacional SQLite com hash de integridade e event log limitado;
- ponte Python que sincroniza NAPA, NeuralModel Hub, ferramentas, Knowledge e adaptadores.

**Conclusão:** K.BA é hoje um runtime de coordenação operacional com plasticidade de roteamento. Não é ainda o mecanismo desenvolvimental da BA.

## 3. Auditoria da BA: lacunas estruturais

| Área | Estado atual | Avaliação |
|---|---|---|
| Organização hierárquica | A proposta documenta regiões/sub-regiões/unidades, mas o grafo Rust atual é plano: capacidades, componentes e conexões | Lacuna estrutural prioritária |
| Nichos ambientais | Benchmarks recentes simulam nichos regionais e topologias em branches separadas | Pesquisa promissora, ainda não integrada |
| Sinalização local | Experimentos 0.7/0.8 estudam comunicação espacial e campos de sinal | Ainda não constitui um sistema de sinalização da BA em execução |
| Plasticidade | Atualização escalar de peso de rota após feedback determinístico validado | Útil para roteamento; não é plasticidade estrutural ou neural |
| Homeostase | Orçamentos e leases protegem recursos de execução | Não há homeostase regional de atividade, conectividade, diversidade e especialização |
| Desenvolvimento | NeuralStem/NeuralDNA documentam estágios, linhagens e predisposições | Ainda não há ciclo integrado de desenvolvimento do fenótipo BA |
| Hereditariedade/evolução | NeuralDNA especifica genoma, epigenoma e recombinação; experimentos permanecem em branches | Não há reprodução computacional multi-geracional integrada |
| Aprendizado ambiental | Feedback de rotas usa resultado determinístico e referência de validação | Não existe ainda adaptação contínua local guiada pelo ambiente |
| Modelos externos | Python/Ollama executam modelos selecionados; Rust planeja | A separação é boa, mas deve permanecer explícita para não confundir BA com IA |

## 4. Pontos fortes confirmados na arquitetura

1. **Separação de planejamento e execução:** o host Rust planeja; a aplicação Python chama o adaptador correspondente. O host não executa texto arbitrário nem comandos de shell.
2. **Contratos e validação:** referências de nós, conexões, IDs, orçamento e executores são validados antes de aceitar um estado.
3. **Feedback restrito:** a ponte envia reforço somente para rotas de ferramentas determinísticas reproduzidas pela Validation Layer. Saídas livres de LLM não são automaticamente tratadas como verdade.
4. **Persistência minimizada:** snapshots evitam prompts, conversas e conteúdo documental; hashes detectam alteração acidental/corrupção.
5. **Controle de execução:** cancelamento, deadline, leases e fila limitada existem como primitives Rust.
6. **Fallback:** a aplicação preserva o caminho anterior quando o host ou o plano K.BA não está disponível.

Esses controles são uma boa fundação operacional, mas não demonstram, isoladamente, adaptação biológica, inteligência geral, evolução ou eficiência superior.

## 5. Riscos e correções necessárias

### P1 — O grafo operacional não pode ser confundido com o tecido da BA

`AdaptiveCognitiveNetwork` representa capacidades e provedores de execução. Um modelo, ferramenta ou memória registrado como `NeuralComponent` não é uma unidade/neurônio da BA.

**Correção proposta:** manter dois domínios explícitos:
- `K.BA Runtime Graph`: capacidades, provedores, executores, dependências e rotas;
- `BA Developmental Substrate`: regiões, sub-regiões, unidades, nichos, campos, receptores, conexões locais, linhagens e estado ambiental.

A ponte entre os domínios deve ser por contratos versionados. Não renomear componentes de execução como neurônios.

### P1 — Falta o ambiente como variável causal do desenvolvimento

Os pesos atuais são atualizados por feedback de sucesso/fracasso, sem estado ambiental regional. Isso não representa seleção local, pressão ecológica, gradientes, competição, disponibilidade de recursos ou mudança de nicho.

**Correção proposta:** cada região recebe um estado ambiental local observável; unidades respondem a sinais locais com sensibilidade, custo e memória de exposição. O ambiente não deve entregar o estado futuro oculto ao agente. A adaptação deve ser avaliada em ambientes estáveis, divergentes, mutáveis e parcialmente observáveis.

### P1 — Plasticidade ainda é uma regra única e sem homeostase estrutural

A atualização atual move um peso em direção ao alvo de feedback. Não há metaplasticidade, consolidação dependente de uso, competição, proteção de funções raras, poda reversível ou balanço de atividade.

**Correção proposta:** estudar mecanismos separáveis: plasticidade rápida, consolidação lenta, metaplasticidade, competição local, homeostase de atividade e reserva de diversidade. Cada mecanismo precisa de ablação e teste de estabilidade antes de coexistir.

### P1 — Leases ainda não controlam todo o ciclo real da aplicação

As primitives de execução controlada existem no Rust, mas o protocolo JSONL v2 é síncrono, o cliente Python serializa chamadas com lock e a integração com workers/Ollama não propaga cancelamento até o backend em todos os caminhos.

**Correção proposta:** integrar cancelamento/deadline ao ciclo de vida real dos workers e ao mecanismo de interrupção do backend, sem prometer interrupção de adaptadores que não suportem cancelamento. Medir fairness e back-pressure sob concorrência.

### P1 — Estimativas de recursos não são contenção física

O `ResourceVector` e o budget são reservas lógicas. Não são cgroups, quotas de VRAM, medição garantida de energia ou controle de frequência da GPU.

**Correção proposta:** separar estimativa, telemetria observada e enforcement. Um componente só pode afirmar contenção física quando o provider/OS confirmar a política aplicada.

### P2 — Persistência local não é criptografia

SQLite usa permissões privadas e hashes de integridade, mas não criptografia em repouso nem proteção contra comprometimento da mesma conta/root. A migração de nome preserva o banco legado quando o destino ainda não existe; conflitos de dois bancos precisam de reconciliação explícita.

### P2 — NAPA não é um sistema de decisão biológica

NAPA classifica áreas por heurísticas lexicais e scores de afinidade não calibrados. Uma área ativada não comprova capacidade nem autoriza execução. Manter essa limitação explícita.

### P2 — BCI/Neuralink é uma integração futura, não parte do núcleo atual

NeuroBridge é uma arquitetura de interoperabilidade separada. A conexão direta com dispositivos Neuralink depende de SDK/API e permissões oficiais. A licença AILU cobre somente os adaptadores, contratos e documentação originais do projeto; não cobre dispositivos, firmware, protocolos fechados, dados, marcas ou propriedade intelectual Neuralink. Qualquer uso futuro deve exigir consentimento informado, minimização de dados, revogação, confirmação humana e revisão clínica/regulatória apropriada. Não há implementação de estimulação neural ou controle de implante.

## 6. Sequência técnica recomendada

1. **Concluir a migração K.BA** e validar build/testes Rust, Python, lint e CI.
2. **Congelar o contrato de fronteira** entre K.BA Runtime Graph e BA Developmental Substrate.
3. **Criar o núcleo espacial da BA em sandbox:** Region, Subregion, Unit, Niche, EnvironmentState, SignalField, Receptor, LocalConnection e HomeostaticBudget.
4. **Validar invariantes:** conservação/fluxo de sinais, estabilidade numérica, isolamento de nichos, ausência de valores inválidos, limites de recursos e determinismo por seed.
5. **Comparar políticas:** local-only, global-only, neighbor, field-based, adaptive-local e hybrid; usar seeds pareadas, ambientes divergentes, perdas de sinal, latência, custos e métricas de pior região.
6. **Adicionar desenvolvimento:** diferenciação e especialização somente após ganho robusto; herança e seleção multi-geracional ficam em etapa própria.
7. **Integrar ao K.BA apenas após evidência:** preservar rollback e não substituir a rota local por consenso global sem comprovação.

## 7. Critério de promoção

Nenhum mecanismo deve ser integrado ao núcleo operacional só por parecer biologicamente plausível. Exigir:
- vantagem reproduzível em múltiplas seeds e ambientes;
- comparação contra baselines simples;
- melhoria na região de pior desempenho, não apenas na média;
- custo de comunicação, memória, CPU/GPU e energia medido;
- ausência de regressão em tarefas raras;
- testes de estabilidade, persistência, restauração e rollback.

## 8. Integridade da migração

A migração de nomenclatura deve preservar o protocolo JSONL v2 e o schema da memória sempre que possível. O cliente prioriza `KBA_RUNTIME_HOST`, mantém compatibilidade temporária com `KIA_RUNTIME_HOST` e com o host legado, e migra o SQLite antigo de forma atômica somente quando o destino novo não existe. Nenhum banco deve ser sobrescrito ou mesclado silenciosamente.

A branch `main` permanece intocada. A alteração é preparada no ramo de integração da PR #14, ainda em Draft, para que as branches experimentais empilhadas possam herdar a nomenclatura após a revisão.
