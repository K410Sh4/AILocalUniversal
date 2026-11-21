# Gerenciamento adaptativo de recursos

O pacote `resources/` contém a primeira implementação do Adaptive Resource Manager.

## Implementado nesta branch

- `contracts.py`: posicionamento sugerido, confiança e contrato de estimativa.
- `estimator.py`: estimativa de pesos por parâmetros totais/quantização e cache KV quando a arquitetura fornece metadados completos.
- `selector.py`: seleção de modelos de chat com preferência, viabilidade estimada e fallback explicado.
- `manager.py`: fachada para snapshot de hardware, estimativas por registro e seleção automática.

## Premissas explícitas

- Pesos: parâmetros totais × bits médios aproximados por parâmetro × fator de segurança 1,12.
- Cache KV: bytes/token extraídos de metadados de arquiteturas densas suportadas, multiplicados pelo contexto solicitado; cache FP16 é assumido.
- Reserva de runtime: 768 MiB por padrão.
- Margem: 15% da memória observada fica reservada.
- O artefato em disco não é usado como estimativa de RAM/VRAM.
- MoE usa parâmetros totais para estimar armazenamento de pesos; parâmetros ativos por token não reduzem o footprint.
- `hybrid` é uma possibilidade teórica que depende de offload suportado pelo runtime; não é uma ordem de execução.

Esses coeficientes são estimativas de planejamento, não medições ou garantias de carregamento. Metadados ausentes geram estado parcial/desconhecido e não são preenchidos por heurística de nome.

## Próximas entregas

- Validar estimativas contra medições locais no Arch e dados do `ollama ps`.
- Registrar benchmark frio/quente de RAM, VRAM, latência, throughput, qualidade e estabilidade.
- Contexto configurável e políticas por tarefa.
- Telemetria contínua, leases, concorrência e ciclo de vida de modelos.
- Integração progressiva com backends além do Ollama.
