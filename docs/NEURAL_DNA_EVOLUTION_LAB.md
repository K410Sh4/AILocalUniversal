# NeuralDNA Evolution Lab — NeuralStem 0.2

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> Estado: protótipo experimental isolado. Não é BA operacional nem modelo biológico celular fiel.

## Objetivo
Estender o NeuralStem 0.1 com linhagens regionais, autorrenovação probabilística, diferenciação, feedback de ocupação, pressão de demanda e limites explícitos de recursos e capacidade.

## Inspiração biológica e tradução computacional
Modelos de neurogênese distinguem células-tronco quiescentes e ativas, autorrenovação simétrica, diferenciação simétrica e divisões assimétricas. Modelos recentes representam ativação e autorrenovação como funções do tamanho das subpopulações e de sinais de feedback. Nichos intrínsecos também podem emergir das interações entre progenitores.

A tradução é deliberadamente menor:
- RegionalNiche: demanda por três destinos, atividade, orçamento e capacidade.
- LineagePolicy: taxa de ativação, saturação tipo Hill, feedback de ocupação, autorrenovação basal, compensação homeostática, pressão de diferenciação, decaimento de potência e limites.
- Cada progenitor ativado divide-se em duas filhas; cada filha permanece progenitora com probabilidade b ou compromete-se com o destino mais compatível.
- A ocupação reduz ativação; baixa ocupação aumenta autorrenovação; demanda elevada favorece diferenciação.
- Decisões pseudoaleatórias são reproduzíveis por seed.

Equações simplificadas:
- occupancy = N / capacity
- activation = clamp(a0 * demand/(K+demand) * (1 - feedback*occupancy) * (0.5 + 0.5*activity), 0, 1)
- b = clamp(b0 + homeostasis*(1-occupancy) - differentiation_pressure*demand, 0, 1)

A função saturante tipo Hill é inspirada em modelos regulatórios, não ajustada a parâmetros fisiológicos.

## Testes e experimentos
- 16 testes locais previstos na suíte test_lineage.py após incluir regressão de capacidade; a execução de CI ainda é necessária para confirmar.
- Varredura exploratória de 373.248 combinações de população, demanda, atividade, recurso, capacidade, ativação, feedback, autorrenovação, homeostase, pressão de diferenciação e custo: invariantes de capacidade, conservação e orçamento preservados. A regra de capacidade foi corrigida para preservar progenitores residentes não selecionados; descendentes que não cabem no nicho diferenciam-se em vez de remover células residentes arbitrariamente.
- A suíte automatizada inclui uma varredura reduzida para CI.
- Os testes não demonstram aprendizagem, inteligência, superioridade evolutiva ou fidelidade biológica.

## Limites conhecidos
- Regiões são simuladas independentemente; comunicação entre regiões e nicho intrínseco multicelular ainda não foram implementados. A diferenciação excedente por capacidade ainda usa o destino dominante do nicho, uma simplificação a comparar com destinos alternativos e quiescência.
- A escolha de destino é dominante, sem múltiplos subtipos por região.
- Não há migração, morte, poda, maturação funcional, conectividade, sinapses ou plasticidade da BA.
- O modelo não substitui NeuralDNA 0.1; acrescenta uma camada experimental de linhagem.

## Próxima etapa
Comparar nichos independentes versus feedback entre regiões; medir estabilidade, cobertura de demanda, diversidade de destinos e custo. Depois adicionar diferenciação em cascata e plasticidade dependente de atividade. Evolução genética aguarda benchmark comparável.

## Referências
- Unraveling regulatory feedback mechanisms in adult neurogenesis through mathematical modelling (2025), npj Systems Biology and Applications: https://doi.org/10.1038/s41540-025-00563-5
- Computational Stem Cell Biology: open questions and guiding principles (2021), Cell Stem Cell: https://doi.org/10.1016/j.stem.2020.12.012
- Dynamic spatiotemporal coordination of neural stem cell fate decisions occurs through local feedback in the adult vertebrate brain (2021): https://pmc.ncbi.nlm.nih.gov/articles/PMC8363814/
- A computational model for the coordination of neural progenitor self-renewal and differentiation through Hes1 dynamics (2015), Development: https://doi.org/10.1242/dev.112649

As pesquisas fundamentam a inspiração, não validam automaticamente esta abstração.

## Propriedade intelectual
Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Código, documentação e schemas originais seguem o aviso proprietário do projeto. Referências e componentes de terceiros mantêm suas autorias e licenças.
