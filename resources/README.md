# Gerenciamento de recursos

Responsabilidades do Resource Manager: monitorar RAM/VRAM/CPU/GPU, estimar custos com incerteza explícita, controlar concorrência, administrar ciclo de vida de modelos e aplicar políticas de memória.

O NeuralModel Hub fornece a primeira camada de descoberta e perfilamento: registra referências de runtime, coleta hardware observável e avalia compatibilidade somente quando requisitos de execução verificados estão disponíveis. O tamanho do artefato em disco não é convertido em requisito de VRAM/RAM.

Próximas entregas: medições por runtime, quantização e contexto; benchmarks frios/quentes; Model Manager com leases; limites de memória e concorrência; scheduler adaptativo.
