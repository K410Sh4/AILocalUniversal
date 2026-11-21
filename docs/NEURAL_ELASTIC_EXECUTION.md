# Neural Elastic Execution

## Objetivo

O Neural Elastic Execution pesquisa estratégias para reduzir a memória residente necessária à execução de modelos grandes, com atenção especial a arquiteturas Mixture of Experts (MoE). A Fase 5.0 entrega um simulador determinístico de políticas de substituição de cache de especialistas.

Esta etapa é um laboratório offline. Ela não modifica o Ollama, o llama.cpp, o NeuralModel Hub, o NeuralMap ou o fluxo de chat.

## O que está implementado na Fase 5.0

O pacote \`neural_elastic/\` fornece:

- contrato \`AccessTrace\` e evento \`ExpertAccess\`;
- parser JSONL validado, com um registro por acesso a especialista;
- cache de capacidade em bytes, inclusive para especialistas de tamanhos diferentes;
- políticas LRU, LFU e estatística com frequência exponencialmente decaída e bônus de recência;
- referência offline Belady MIN, restrita a especialistas de tamanho uniforme;
- gerador determinístico de rastros sintéticos estacionários, uniformes e com fases;
- comparação das políticas por hit rate, miss rate, bytes lidos simulados, leituras por token, evictions, bypass e ocupação máxima;
- CLI \`neural-elastic-sim\` e módulo \`python -m neural_elastic.cli\`.

A política estatística é uma baseline explicável; não é um modelo neural treinado. O pacote define uma base extensível para políticas futuras, mas ainda não treina nem executa um Expert Predictor neural.

## Formato de trace JSONL

Cada linha representa um acesso a um especialista. Vários especialistas selecionados para o mesmo token compartilham \`token_index\`; a ordem das linhas é a ordem de acesso observada.

\`\`\`jsonl
{"token_index":0,"expert_id":"layers.0.experts.4","size_bytes":16777216}
{"token_index":0,"expert_id":"layers.0.experts.9","size_bytes":16777216}
{"token_index":1,"expert_id":"layers.0.experts.4","size_bytes":16777216}
{"token_index":2,"expert_id":"layers.1.experts.2","size_bytes":25165824}
\`\`\`

Regras do contrato:

- \`token_index\` é inteiro não negativo e não decrescente;
- \`expert_id\` é uma string não vazia e deve identificar globalmente camada e especialista;
- \`size_bytes\` é inteiro positivo e precisa permanecer constante para um mesmo especialista no trace;
- a ordem dos registros precisa preservar a sequência de acesso que se deseja simular;
- linhas vazias são ignoradas; comentários e JSON malformado são rejeitados.

Os rastros reais devem vir de um runtime instrumentado que registre a decisão do roteador e a identidade/tamanho dos especialistas. A API de chat do Ollama usada nesta versão transmite conteúdo gerado e métricas agregadas, mas não expõe a sequência de IDs dos especialistas MoE. Portanto, os benchmarks de tokens/s executados com Qwen3-Coder-Next não são traces de roteamento e não podem ser convertidos em traces reais por inferência.

## Políticas comparadas

| Política | Decisão |
|---|---|
| LRU | Remove o item residente menos recentemente utilizado. |
| LFU | Remove o item residente menos frequentemente utilizado; recência desempata. |
| Statistical | Combina frequência histórica com decaimento exponencial e bônus de recência. |
| Belady MIN | Remove o item cujo próximo acesso está mais distante, conhecendo todo o futuro. |

Belady MIN é um oráculo offline. Com itens de tamanho uniforme, fornece a referência ótima de misses para o modelo clássico de cache de capacidade fixa. O simulador recusa essa comparação quando os especialistas têm tamanhos diferentes, porque escolher o próximo uso mais distante não é, em geral, uma solução ótima para objetos de tamanhos variáveis. Ele não é uma política online disponível durante inferência.

## Métricas

- **Hit/miss:** acessos atendidos pelo cache ou que exigiriam carregamento.
- **Bytes lidos:** soma do tamanho de cada acesso que sofreu miss. É I/O simulado, não leitura física medida.
- **Bytes por token:** bytes simulados divididos pela quantidade de índices de token distintos.
- **Evictions:** quantidade de especialistas removidos para abrir espaço.
- **Bypass:** misses para especialistas maiores que toda a capacidade; eles não expulsam itens residentes.
- **Peak resident:** maior ocupação em bytes e maior número de especialistas residentes.

Todas as políticas começam com cache frio e recebem exatamente a mesma sequência de acessos e capacidade.

## Executar

Trace sintético determinístico:

\`\`\`bash
.venv/bin/neural-elastic-sim --synthetic \\
  --tokens 10000 --experts 64 --top-k 2 \\
  --expert-mib 4 --capacity-mib 64 \\
  --workload phased --phase-tokens 500 --seed 42
\`\`\`

Relatório JSON:

\`\`\`bash
.venv/bin/neural-elastic-sim --synthetic --json
\`\`\`

Trace instrumentado:

\`\`\`bash
.venv/bin/neural-elastic-sim --trace ./expert-accesses.jsonl \\
  --capacity-mib 512 --json
\`\`\`

Também é possível executar \`python -m neural_elastic.cli\` dentro do ambiente virtual.

## Limites deliberados desta fase

O simulador é um modelo de substituição de cache, não um simulador completo de inferência. Ainda não modela:

- latência, largura de banda, fila ou concorrência do SSD;
- page cache do sistema operacional, mmap, DMA ou transferência PCIe;
- pré-carregamento (prefetch), sobreposição de I/O e computação ou execução assíncrona;
- roteamento real, topologia de camadas, sincronização e kernels de CPU/GPU;
- fragmentação, buffers temporários, cache KV ou memória do runtime;
- qualidade de resposta, energia, temperatura ou tokens por segundo;
- acesso parcial a tensores ou granularidade interna dos formatos de pesos.

A capacidade do simulador representa apenas o orçamento de cache de especialistas definido no teste. Não equivale à RAM/VRAM total e não prova que um modelo cabe em determinada máquina.

Os traces sintéticos servem para verificar comportamento e comparar algoritmos em condições controladas. Não comprovam aceleração em hardware real nem devem ser apresentados como rastros coletados de modelos publicados.

## Próximas etapas de pesquisa

1. Instrumentar um runtime de referência para capturar IDs de especialistas, camada, token, tamanho e ordem de solicitação.
2. Preservar traces reais anonimizados/sem conteúdo de prompt e documentar modelo, versão, quantização e configuração da coleta.
3. Comparar as políticas neste simulador antes de adicionar predição neural.
4. Estender o simulador com tempos de serviço, largura de banda e prefetch, validando o modelo contra medições físicas.
5. Integrar a política vencedora a um protótipo de runtime isolado, sem alterar o caminho Ollama estável do aplicativo.

O critério de avanço não é apenas aumentar hit rate: precisamos demonstrar redução de bytes transferidos e/ou latência no runtime, sem ultrapassar a memória disponível nem degradar a qualidade.
