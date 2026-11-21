# NeuralDNA Evolution Lab — NeuralStem 0.1

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

> Estado: protótipo experimental isolado. Não é BA operacional, não treina LLMs e não afirma equivalência com células-tronco biológicas.

## Objetivo

Validar a primeira etapa genótipo → desenvolvimento: um programa NeuralDNA compacto orienta unidades progenitoras artificiais (NeuralStem) a diferenciarem-se em três classes abstratas — memória, associação e controle — conforme sinais locais (NicheState) e orçamento de recursos.

A inspiração é funcional: em sistemas biológicos, destino celular depende da interação entre programas intrínsecos e sinais do nicho. O protótipo traduz isso em loci numéricos tipados e sinais explícitos; não simula genes, proteínas, morfogênios ou biologia celular real.

## Modelo v0.1

- Genoma: afinidades por destino, limiar de diferenciação, viés de autorrenovação, sensibilidade à atividade e custo unitário.
- Nicho: demanda local por destino, atividade e recurso disponível.
- NeuralStemCell: potência e profundidade de linhagem.
- Desenvolvimento: escolhe o destino de maior compatibilidade, respeita limiar e orçamento e conserva unidades não diferenciadas como progenitoras.
- Determinismo: entradas idênticas produzem a mesma saída; não há aleatoriedade implícita.

Cada progenitor termina como uma unidade diferenciada ou permanece como progenitor. A versão atual não multiplica células nem modela migração, morte, poda, conectividade ou plasticidade sináptica.

## Testes executados antes de integrar

Ambiente local isolado, Python 3.11+:

| Teste | Resultado |
|---|---|
| Seleção de destino por sinal do nicho | aprovado |
| Limite de recurso e diferenciação parcial | aprovado |
| Sinais insuficientes preservam progenitores | aprovado |
| Determinismo | aprovado |
| Rejeição de loci fora do domínio | aprovado |
| Rejeição de orçamento inválido | aprovado |
| Conservação da população | aprovado |

Resultado: **7 testes aprovados**. compileall aprovado. Ruff não estava instalado no ambiente de prototipagem; lint não foi declarado como aprovado.

## Interpretação e limites

Os testes confirmam apenas propriedades locais do simulador. Não demonstram que a diferenciação artificial melhora a aprendizagem, que a evolução de genomas é mais eficiente que a evolução direta de redes, nem que os três destinos representam áreas cerebrais reais.

O mecanismo atual escolhe um único destino dominante por nicho. Isso isola a primeira variável. Próximas experiências devem comparar seleção exclusiva versus diferenciação proporcional/competitiva, incluir autorrenovação com divisão limitada e testar múltiplos nichos regionais.

## Próxima bateria experimental

1. Comparar progenitores sem diferenciação, diferenciação por regra fixa e diferenciação regulada pelo nicho.
2. Variar demanda, atividade, limiar, potência, custo e orçamento em desenho fatorial com múltiplas seeds.
3. Medir diversidade de destinos, cobertura de demanda, custo, estabilidade e sensibilidade a perturbações.
4. Adicionar divisão/autorrenovação apenas após definir limites de população e evitar crescimento explosivo.
5. Integrar evolução genética (seleção, crossover e mutação) somente quando o desenvolvimento isolado tiver benchmarks reproduzíveis.
6. Implementar o núcleo validado em Rust após estabilizar contratos e métricas em Python.

## Fundamento científico

- Miikkulainen (2025), Neuroevolution insights into biological neural computation, Science. Discute sinergia entre evolução, desenvolvimento e aprendizagem e ressalta que evidência computacional não prova mecanismos biológicos: https://doi.org/10.1126/science.adp7478
- Genetics of human brain development (2023/2024), Nature Reviews Genetics. Revisão sobre regulação genética espaço-temporal do desenvolvimento cerebral: https://doi.org/10.1038/s41576-023-00626-5
- Complex computation from developmental priors (2023), Nature Communications. Exemplo de codificação neurodesenvolvimental em que regras de compatibilidade neuronal geram conectividade: https://doi.org/10.1038/s41467-023-37980-1

As ideias e resultados dos artigos pertencem aos respectivos autores. Este documento descreve a tradução experimental original do projeto AILocal Universal.

## Propriedade intelectual

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

Código, documentação e schemas originais deste laboratório seguem o aviso proprietário do projeto. Referências científicas, dados e componentes de terceiros mantêm suas autorias e licenças.
