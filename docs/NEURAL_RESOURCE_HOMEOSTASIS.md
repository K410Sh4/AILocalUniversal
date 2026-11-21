# Neural Resource Homeostasis — princípios biológicos para o AILocal

Copyright © 2026 K410Sh4. All rights reserved.  
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary

## Propósito

Este documento formaliza uma linha de pesquisa para o Adaptive Resource Manager, Neural Elastic Execution e K.IA: administrar modelos, contexto, memória e capacidade computacional como um ecossistema adaptativo, inspirado em princípios estruturais da neurobiologia.

A inspiração é algorítmica, não uma alegação de equivalência entre cérebro e computador. RAM, VRAM, SSD, pesos de modelos e sinapses são entidades físicas diferentes. A transferência válida está nos princípios de organização, adaptação, economia e estabilidade.

## 1. Princípios biológicos relevantes

### 1.1. Codificação esparsa e alocação competitiva

Memórias biológicas são associadas a conjuntos distribuídos e relativamente esparsos de neurônios. A alocação não é uniforme: neurônios elegíveis competem, e a excitabilidade influencia quais entram em um conjunto de memória. A sobreposição pode favorecer integração; a separação pode reduzir interferência.

**Tradução para o AILocal:**
- Ativar somente capacidades, ferramentas, modelos e regiões da BA relevantes para a tarefa.
- Permitir que caminhos recorrentes ganhem prioridade por utilidade medida, não apenas por frequência.
- Preservar rotas alternativas para evitar dependência rígida de um único componente.
- Evitar manter todos os modelos e subsistemas ativos apenas porque estão instalados.

A seleção deve considerar adequação à tarefa, qualidade validada, custo incremental, latência, reutilização e pressão de memória.

### 1.2. Sinapses com múltiplas escalas temporais

Modelos de consolidação sináptica descrevem variáveis rápidas e lentas. Alterações transitórias podem explorar novas configurações; componentes persistentes estabilizam o que demonstrou utilidade. O armazenamento em múltiplas escalas ajuda a equilibrar adaptação, retenção e custo.

**Tradução para o AILocal:**

| Escala | Analogia funcional | Recurso no AILocal |
|---|---|---|
| Imediata | atividade transitória | buffers, requisição, leases e contexto ativo |
| Curta/média | traço temporário | cache de tarefa, resultados intermediários e especializações temporárias |
| Persistente | conexão estabilizada | modelos residentes, metadados calibrados e políticas validadas |
| Longo prazo | memória distribuída | catálogo, conhecimento/RAG, NeSA e histórico agregado de desempenho |

O sistema não deve promover automaticamente um comportamento transitório a uma política permanente. A promoção exige repetição, benefício mensurável e ausência de regressões.

### 1.3. Homeostase sináptica

A homeostase regula a atividade global para evitar saturação. A hipótese de homeostase sináptica propõe que o fortalecimento associado à aprendizagem precisa ser contrabalançado por processos de renormalização e seleção.

**Tradução para o AILocal:**
- Manter uma reserva global de RAM/VRAM para o sistema, interface, drivers e processos externos.
- Normalizar a pressão de recursos antes de admitir novas tarefas.
- Reduzir prioridade de componentes pouco úteis sob pressão, sem destruir conhecimento ou preferências persistentes.
- Distinguir ocupação já existente de nova alocação.

A reserva é um limite operacional, não um mecanismo de apagamento. A pressão deve primeiro reduzir trabalho transitório, concorrência e buffers opcionais; descarregar modelos exige verificar leases e confirmar o unload.

### 1.4. Replay e consolidação

O replay de padrões de atividade é associado à consolidação, integração e planejamento. Estudos computacionais mostram como replay, poda seletiva e escalonamento homeostático podem ser combinados para aumentar robustez e esparsidade.

**Tradução para o AILocal:**
- Executar benchmarks e reavaliações fora do caminho crítico.
- Reproduzir traces sintéticos ou anonimizados de tarefas, sem persistir prompts privados por padrão.
- Atualizar estimativas por modelo, hardware, contexto, backend e quantização somente após medições repetidas.
- Manter snapshots e versões de política para reverter calibrações que piorem latência, qualidade ou estabilidade.

Replay aqui significa reavaliar comportamento técnico, não repetir conversas privadas.

### 1.5. Poda seletiva

Poda biológica não equivale a apagar aleatoriamente conexões fracas. A utilidade, o contexto, a competição e a estabilidade importam.

**Tradução para o AILocal:**
- Priorizar a liberação de caches temporários expirados.
- Descarregar modelos com baixo valor de reutilização quando a pressão justificar o custo de recarga.
- Considerar custo de cold-start, frequência, especialização, latência e dependências.
- Nunca descarregar um modelo com tarefa ativa ou lease não liberado.
- Confirmar a ausência do modelo em `/api/ps` antes de marcar sua memória como liberada.

## 2. Hierarquia de memória proposta

A hierarquia é inspirada na distribuição funcional da memória biológica, mas implementada com mecanismos reais do sistema operacional e dos runtimes.

1. **Hot — contexto ativo:** tokens, KV cache, buffers e estado de execução da tarefa atual.
2. **Warm — residência:** modelos já carregados e recursos de runner reservados.
3. **Cold — armazenamento local:** artefatos de modelos, pacotes `.neuralinjector`, índices e dados persistentes.
4. **Associativa — conhecimento:** RAG, NeSA, metadados e relações recuperáveis.
5. **Consolidada — política:** parâmetros adaptativos e perfis que passaram por validação.

O SSD não deve ser tratado como RAM mais lenta de forma automática. A ideia de regiões e sub-regiões pode organizar dados, índices e caches, mas a velocidade depende de paginação, mmap, prefetch, layout, sistema de arquivos e padrão de acesso. Ganho deve ser demonstrado por benchmark.

## 3. Modelo de decisão — proposta experimental

Uma política futura pode calcular a utilidade de manter ou ativar um componente:

```text
utility =
    task_relevance
  + validated_quality
  + reuse_frequency
  + reload_cost_avoided
  - latency_penalty
  - memory_pressure
  - energy_or_compute_cost
  - interference_risk
```

Os termos devem ser normalizados por hardware e tarefa. Os coeficientes não são probabilidades e não devem ser fixados por intuição. Devem ser calibrados em traces e benchmarks, com limites de segurança e comparação contra uma política de referência.

A admissão precisa obedecer:

```text
available_after_reserve >= incremental_requirement
```

O requisito incremental deve incluir somente alocações que ainda não existem. A memória já ocupada por um modelo residente não pode ser subtraída novamente do sistema livre nem somada uma segunda vez como se fosse um novo carregamento.

## 4. Contabilidade fria versus residente

### Carregamento frio

Quando não há identidade residente comprovada, usar o estimador conservador atual:

```text
cold = weights + KV(context) + runtime_overhead
```

### Reutilização residente

Quando referência e digest coincidem, o runner reporta footprint válido e o contexto solicitado cabe na capacidade configurada, os pesos, KV e buffers já alocados não devem ser somados novamente ao orçamento de uma nova solicitação serial.

A etapa implementada em `resources.residency.assess_resident_capacity()` aplica essas condições e retorna `incremental_runner_bytes = 0` somente nesse caso. Isso significa zero nova alocação do runner para reutilizar a capacidade existente; não significa consumo zero do processo, da aplicação ou do sistema.

O caminho rápido é bloqueado quando:
- digest não coincide ou está ausente;
- snapshot está ambíguo;
- tamanho total, VRAM ou contexto estão ausentes/inconsistentes;
- contexto pedido excede o contexto configurado;
- janela declarada do modelo é excedida;
- mais de uma solicitação concorrente é pedida sem telemetria de slots suficiente.

Nesses casos, o chamador deve retornar ao cálculo frio ou aguardar uma política de concorrência validada.

### Significado dos campos Ollama

O endpoint `GET /api/ps` informa `size`, `size_vram`, `digest` e `context_length`. No código upstream atual do runner llama.cpp, o tamanho total é composto por buffers de modelo, KV e computação; a parcela GPU é contabilizada separadamente. O campo de contexto descreve a capacidade configurada do runner, não o número de tokens atualmente ocupados.

O AILocal preserva os campos reportados e não deduz RAM por simples subtração para tomar decisões. Versões e runners diferentes podem reportar de formas distintas; o caminho de reutilização exige telemetria completa e não transforma esses números em uma decomposição universal de pesos/KV.

## 5. Ciclo de controle adaptativo

```text
OBSERVE
  -> CLASSIFY (cold / resident / unknown)
  -> PREDICT (full or incremental)
  -> ADMIT (respect global reserve)
  -> EXECUTE (leases and bounded concurrency)
  -> MEASURE (RAM, VRAM, latency, errors, quality)
  -> CONSOLIDATE (repeated validated evidence)
  -> PRUNE (only expired, unleased, low-utility resources)
```

Cada decisão deve registrar a evidência, a política aplicada e a razão do fallback. A telemetria não deve armazenar prompts, conteúdo documental ou respostas por padrão.

## 6. Fases de implementação

- **Fase A — identidade residente:** concluída; referência exata + digest.
- **Fase B — capacidade residente:** concluída; avaliação pura com digest, footprint, contexto, frescor e expiração.
- **Fase C — integração do seletor:** concluída; snapshots do Engine Adapter alimentam a seleção Automática e o planner ACCA/K.IA, com fallback frio e modo Manual preservado.
- **Fase D — leases e concorrência:** leases locais de uso/mutação implementadas na aplicação; Chat bloqueia pull/remoção enquanto usa o modelo. Ainda faltam slots reais, leases compartilhadas Rust/Ollama, cancelamento coordenado e confirmação de unload externo. Snapshots só podem habilitar reutilização se a observação tiver até 30 segundos e a expiração estiver a mais de 2 segundos.
- **Fase E — calibração empírica:** probe PSS/RSS Linux implementado para a árvore Ollama; falta conectar sessões controladas de load/inferência/unload, medir VRAM e calibrar por hardware.
- **Fase F — homeostase adaptativa:** calibrar prioridade, retenção, descarregamento e consolidação com traces reproduzíveis e rollback.

Nenhuma fase posterior deve ser marcada como concluída apenas por analogia biológica ou teste sintético.

## 7. Referências científicas e técnicas

- Brea, J. et al. (2025). *Two-factor synaptic consolidation reconciles robustness with pruning and homeostatic scaling*. PNAS. https://pmc.ncbi.nlm.nih.gov/articles/PMC12595459/
- Li, H. & van Rossum, M. C. W. (2020). *Energy efficient synaptic plasticity*. eLife 9:e50804. https://doi.org/10.7554/eLife.50804
- Benna, M. K. & Fusi, S. (2016). *Computational principles of synaptic memory consolidation*. Nature Neuroscience 19, 1697–1706. https://doi.org/10.1038/nn.4401
- Josselyn, S. A. & Frankland, P. W. (2018). *Memory Allocation: Mechanisms and Function*. Annual Review of Neuroscience 41, 389–413. https://doi.org/10.1146/annurev-neuro-080317-061956
- Ollama API, `/api/ps`: https://github.com/ollama/ollama/blob/main/docs/openapi.yaml
- Ollama llama.cpp runner memory accounting: https://github.com/ollama/ollama/blob/main/llm/llama_server.go
- Linux procfs, PSS/RSS em `smaps` e `smaps_rollup`: https://man7.org/linux/man-pages/man5/proc_pid_smaps.5.html
- Linux kernel, cgroup v2 memory accounting: https://docs.kernel.org/admin-guide/cgroup-v2.html
