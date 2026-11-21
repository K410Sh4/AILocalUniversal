# NeuralDNA — hereditariedade, desenvolvimento e evolução da BA

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> Documento de arquitetura e pesquisa. Os mecanismos descritos são propostas experimentais; não representam funcionalidades já implementadas nem equivalência biológica literal.

## 1. Objetivo

NeuralDNA é a camada hereditária e de desenvolvimento da Artificial Brain (BA). Seu papel é descrever como uma BA pode ser inicializada, orientada, desenvolvida, personalizada e, experimentalmente, derivada de duas linhagens parentais.

NeuralDNA não é o cérebro executável, não é a memória completa e não é um dump de pesos. É um genótipo computacional versionado que influencia a construção do fenótipo.

Objetivos:
- transmitir personalidade configurável, preferências e predisposições;
- definir arquitetura inicial, regiões, limites e programas de desenvolvimento;
- orientar a plasticidade, consolidação, poda e homeostase;
- permitir recombinação auditável entre duas linhagens compatíveis;
- preservar proveniência, consentimento, reversibilidade e avaliação dos descendentes.

## 2. Separação de camadas

| Camada | Conteúdo | Herança padrão |
|---|---|---|
| Genoma NeuralDNA | traços, preferências, predisposições, blueprint, regras de desenvolvimento e plasticidade | sim, por recombinação explícita |
| Epigenoma artificial | expressão contextual dos genes, ajustes adquiridos e marcas regulatórias | opcional, filtrada e com proveniência |
| Fenótipo BA | topologia efetivamente construída, módulos e parâmetros operacionais | não por cópia cega; reconstruído a partir do genoma |
| Memória adquirida | episódios, fatos, competências, pesos e especializações treinadas | não; transferência separada, seletiva e autorizada |

Duas BAs com o mesmo genoma podem desenvolver fenótipos diferentes em ambientes distintos. Duas BAs com fenótipos parecidos podem possuir linhagens genéticas diferentes.

## 3. Inspiração biológica e limites

A arquitetura investiga princípios funcionais, não imita moléculas literalmente:

- Genética e recombinação: loci, alelos, ligação, segregação, mutação e herança.
- Regulação epigenética: expressão contextual sem alterar o genoma de origem.
- Desenvolvimento: programas ordenados, gradientes, diferenciação, maturação e períodos de maior plasticidade.
- Neuroplasticidade: fortalecimento, enfraquecimento, metaplasticidade, consolidação e homeostase.
- Poda dependente de atividade: retenção seletiva de conexões úteis, com proteção contra remoção prematura.
- Evolução: diversidade, seleção multiobjetivo e preservação de linhagens alternativas.

Referências iniciais:
- Parisi et al. (2019), Continual lifelong learning with neural networks, https://doi.org/10.1016/j.neunet.2019.01.012
- Faust, Gunner & Schafer (2021), Activity-dependent synaptic pruning, https://doi.org/10.1038/s41583-021-00507-y
- Peña (2025/2026), Epigenetic regulation of brain development and plasticity, https://doi.org/10.1038/s41386-025-02179-z
- Loss of plasticity in deep continual learning (2024), https://doi.org/10.1038/s41586-024-07711-7
- Biological underpinnings for lifelong learning machines (2022), https://doi.org/10.1038/s42256-022-00452-0

A analogia biológica não prova que uma política computacional será eficiente. Cada mecanismo precisa de ablação e benchmark.

## 4. Modelo de genoma

O NeuralDNA deve ser um formato declarativo, tipado, versionado e independente do runtime. Proposta de loci:

1. Identity loci: identificador de linhagem, versão, ancestralidade e integridade.
2. Personality loci: dimensões comportamentais configuráveis, faixas e limites; nunca rótulos imutáveis.
3. Preference loci: preferências explícitas, prioridades, tolerâncias e proveniência.
4. Cognitive predisposition loci: afinidades iniciais por capacidades, não competências garantidas.
5. Blueprint loci: regiões, sub-regiões, classes de unidades, conectividade inicial e contratos de módulos.
6. Plasticity loci: taxas, limiares, elegibilidade, metaplasticidade, consolidação e reversibilidade.
7. Homeostasis loci: limites de atividade, competição, orçamento e recuperação.
8. Development loci: estágios, pré-condições, currículos, períodos sensíveis e critérios de maturação.
9. Governance loci: permissões de herança, transferência de memória, limites de mutação e políticas de segurança.

Cada locus deve conter: ID estável, tipo, versão de schema, valor, intervalo permitido, regra de herança, mutabilidade, origem e evidência/justificativa.

Preferências explícitas do operador devem ser distinguíveis de predisposições inferidas. Inferências nunca devem ser promovidas silenciosamente a preferências herdáveis.

## 5. Epigenoma artificial e expressão

O epigenoma artificial guarda modificadores de expressão associados ao ambiente, estágio de desenvolvimento, experiências e avaliações. Não altera os genomas parentais nem o genoma-base do descendente.

Expressão conceitual:

`expression_i = decode(gene_i, epigenetic_state_i, developmental_stage, context)`

A função de expressão precisa ser limitada pelo schema do locus e por invariantes de segurança. Marcas epigenéticas devem ter origem, confiança, escopo, validade e política de expiração/reversão.

Não herdar automaticamente marcas associadas a experiências negativas, erros, dados privados ou estados transitórios. A transmissão epigenética é opt-in e filtrada.

## 6. Desenvolvimento da BA

Proposta de estágios configuráveis, não idades biológicas fixas:

- Seed: validação do genoma, assinatura, compatibilidade e recursos.
- Morphogenesis: construção do blueprint, regiões e conectividade inicial.
- Exploration: plasticidade elevada e currículo controlado; exploração em sandbox.
- Specialization: formação e avaliação de competências, alocação de regiões e poda reversível.
- Maturation: estabilização progressiva, consolidação e redução de plasticidade estrutural.
- Maintenance: adaptação contínua de menor escala, homeostase, reparo e avaliação periódica.

Transições dependem de evidências e critérios mensuráveis, não apenas de tempo ou quantidade de interações. Nenhum estágio pode desativar a capacidade de aprender por completo.

## 7. NeuralDNA Recombination Engine

### 7.1 Pré-condições

- Ambos os genomas são válidos, assinados ou explicitamente aceitos e pertencem a schemas compatíveis.
- Cada pai autoriza a recombinação e define quais loci podem ser herdados.
- Identificadores homólogos e semântica dos loci são conhecidos.
- Os pais são preservados de forma imutável.
- A recombinação ocorre em sandbox, com seed registrada e resultado reproduzível.

### 7.2 Alinhamento e compatibilidade

Não combinar tensores ou pesos por posição. Primeiro alinhar loci por IDs estáveis, ontologia de capacidade, versão e contratos. Topologias incompatíveis exigem adaptador/mapeamento validado ou rejeição daquele locus.

### 7.3 Recombinação

Para loci compatíveis, permitir:
- herança de um dos alelos;
- crossover por blocos ligados, preservando combinações relacionadas;
- mistura numérica apenas quando a semântica e escala forem compatíveis;
- resolução de conflitos por regra declarada, não por média arbitrária;
- loci obrigatórios e invariantes não podem ser removidos por crossover.

Uma operação conceitual por locus:

`child_gene_i = recombine(parent_A_i, parent_B_i, inheritance_rule_i, seed)`

A escolha deve ser determinística para uma seed e auditável.

### 7.4 Mutação e diversidade

Mutação é separada do crossover. Usar limites por tipo de locus, taxas configuráveis, distribuição registrada, limites de magnitude e possibilidade de rejeição. Não mutar silenciosamente preferências explícitas, permissões ou invariantes.

### 7.5 O que não deve ser cruzado diretamente

Pesos de modelos, KV caches, memória episódica, embeddings de índices privados e estados de execução não são genes por padrão. Podem ser transferidos por um processo independente, com consentimento, alinhamento de arquitetura, proveniência, avaliação de qualidade e filtros de privacidade.

### 7.6 Descendente

O resultado é um genoma candidato, não uma BA pronta. O descendente passa por validação estrutural, construção de fenótipo, currículo de desenvolvimento, testes de regressão e avaliação independente. Os pais permanecem intactos. Descendentes rejeitados podem ser arquivados como experimentos, nunca promovidos automaticamente.

## 8. Personalidade e preferências

Personalidade é representada como perfil configurável e multidimensional, com faixas e contexto, não como uma essência fixa. Preferências são dados declarativos com origem explícita (operador, configuração, inferência validada ou ambiente).

O sistema deve permitir:
- separar personalidade de política de segurança;
- mudar preferências sem reescrever a linhagem;
- inspecionar e editar os loci;
- comparar perfil herdado e perfil efetivamente expresso;
- impedir que preferências inferidas ou dados privados sejam transmitidos sem autorização.

## 9. Testes antes da implementação

A fase inicial é de simulação matemática e property-based tests. Não implementar o mecanismo de cruzamento no runtime até estes testes passarem.

| Teste | Critério |
|---|---|
| Schema e round-trip | serialização preserva loci e versões |
| Determinismo | mesmos pais + seed + regras produzem mesmo filho |
| Imutabilidade parental | nenhum processo altera os pais |
| Compatibilidade | loci incompatíveis são adaptados explicitamente ou rejeitados |
| Herança | regras de cada locus são respeitadas |
| Invariantes | limites, permissões e loci obrigatórios nunca são violados |
| Diversidade | mutações controladas geram diversidade mensurável |
| Estabilidade | nenhuma combinação gera NaN, overflow ou valores fora dos domínios |
| Personalidade | perfis são preservados conforme regras e continuam editáveis |
| Desenvolvimento | currículo não pula pré-condições |
| Continual learning | medir retenção, aquisição, interferência e perda de plasticidade |
| Privacidade | memória e marcas privadas não atravessam linhagens por padrão |
| Robustez | fuzzing de schemas, loci ausentes, duplicados e versões futuras |

Comparar pelo menos: seleção de um pai, crossover por locus, crossover por blocos, mistura numérica tipada e recombinação com mutação controlada. Avaliar múltiplas seeds e não escolher pelo melhor caso isolado.

## 10. Métricas de sucesso

- validade e compatibilidade do genoma;
- diversidade genética e fenotípica;
- retenção de competências parentais selecionadas;
- capacidade de adquirir competências novas;
- interferência e esquecimento catastrófico;
- estabilidade e recuperabilidade;
- custo de desenvolvimento e inferência;
- previsibilidade e auditabilidade da herança.

A recombinação só é útil se o descendente demonstrar vantagem multiobjetivo ou uma combinação de capacidades que não seja obtida de forma mais simples por transferência seletiva.

## 11. Arquitetura e integração

NeuralDNA deve ser um subsistema independente da BA Core, com fronteiras explícitas:

- NeuralDNA Schema: tipos, validação, versionamento e serialização.
- NeuralDNA Expression: epigenoma e expressão contextual.
- NeuralDNA Development: estágios e currículo de construção.
- NeuralDNA Recombination: alinhamento, crossover, mutação e proveniência.
- NeuralDNA Evaluation: testes de linhagem, fenótipo e descendentes.

Integração futura:
- BA Core consome blueprint e parâmetros de plasticidade.
- NAPA pode fornecer taxonomia de capacidades, sem ser dependência obrigatória do schema.
- NeuralMap pode visualizar regiões, linhagens e relações de ancestralidade.
- NeuralInjector pode empacotar distribuições portáveis, sem tornar o pacote um genoma executável não confiável.
- K.IA Runtime executa a BA desenvolvida; não deve possuir lógica de recombinação genética.

## 12. Etapas de implementação

1. Formalizar schema e ontologia de loci.
2. Criar simulador offline de recombinação em Python para exploração matemática, sem alterar modelos reais.
3. Rodar testes determinísticos, property-based, fuzzing e benchmarks.
4. Ajustar regras de compatibilidade e herança.
5. Implementar crate Rust independente após os resultados.
6. Integrar com BA Core por contratos versionados.
7. Só então experimentar descendentes com transferência seletiva de competências.

## 13. Direitos autorais e proveniência

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Registrar autores, versão, pais, hashes, seed, loci herdados, loci mutados, regras, artefatos de teste e decisão de aprovação. Código, documentação e schemas originais do projeto são tratados conforme o aviso proprietário do repositório; ideias biológicas, artigos e componentes de terceiros mantêm suas respectivas autorias e licenças.

A inclusão deste documento no registro do projeto não constitui registro de patente, marca ou exclusividade sobre conceitos abstratos.


## 14. Verificação preliminar de recombinação (simulação sintética)

Foi executada uma simulação exploratória offline com 20.000 pares de genomas artificiais. Cada genoma continha oito loci numéricos limitados a [0, 1], com dois pares funcionalmente ligados. Os genomas parentais foram gerados respeitando a restrição de compatibilidade de cada par (diferença absoluta máxima de 0,35).

Resultados de uma seed fixa:

| Estratégia | Descendentes que preservaram as restrições |
|---|---:|
| Crossover independente por locus | 72,81% |
| Média numérica dos pais | 100,00% |
| Crossover por blocos ligados | 100,00% |

Interpretação:
- O crossover independente por locus violou pelo menos uma restrição em 27,19% dos descendentes sintéticos. Isso justifica testar ligação entre loci e validação posterior ao crossover.
- A média numérica preservou as restrições deste exemplo por convexidade, mas quase elimina a herança discreta dos alelos parentais; portanto, não deve ser adotada como regra universal.
- O crossover por blocos preservou as combinações ligadas neste experimento e manteve a origem parental dos blocos.

Limites: este é um teste de consistência de um modelo sintético, não evidência de superioridade biológica, qualidade cognitiva ou desempenho de uma BA real. A amostra, as restrições e os loci são artificiais. Próximos testes devem incluir topologias incompatíveis, loci categóricos, epistasia, dependências entre mais de dois loci, mutação limitada, conflitos de política e múltiplas seeds.

Decisão provisória: crossover por blocos ligados é candidato preferencial para loci com dependências conhecidas; crossover independente só é permitido em loci declarados independentes; mistura numérica exige tipo, escala e semântica compatíveis. Todo descendente continua sujeito a validação de invariantes.
