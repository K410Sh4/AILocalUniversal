# Adaptive Hardware & Graceful Degradation

Complemento da NIP 0.1.0. Consulte a seção 6A em [NIP 0.1.0](NEURALINJECTOR_NIP_0.1.0.md), os [perfis](../examples/neuralinjector/hardware/profiles/) e o [planejador](../core/neuralinjector/resources.py).

O planejador inicial detecta RAM/CPU pela biblioteca padrão, seleciona entre quatro perfis, cria orçamento e relatório. GPU/VRAM dependem de integração explícita. Não há quantização, poda, offloading ou restauração de pesos implementados por este módulo.
