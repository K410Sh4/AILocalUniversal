# K.IA 0.5 — Execution Safety Core

## Objetivo

Introduzir limites verificáveis para a execução de tarefas e para a reserva concorrente de recursos, sem transformar o RuntimeHost JSONL em serviço de rede nem afirmar que reservas lógicas são quotas físicas.

## Controle por tarefa

ExecutionControl é um token compartilhável entre as partes de uma tarefa. Ele contém um sinal atômico de cancelamento e um deadline absoluto opcional, calculado na criação do controle.

A chamada de execução verifica o estado antes de adquirir recursos, durante a espera por um lease e depois que o adaptador retorna. O deadline inclui o tempo gasto aguardando recursos e executando componentes. Cancelamento tem precedência quando cancelamento e deadline são observados ao mesmo tempo.

## Adaptadores cooperativos

ComponentExecutor ganhou execute_controlled com implementação padrão compatível que verifica o controle antes de delegar ao execute existente. Adaptadores que podem ficar bloqueados devem sobrescrever execute_controlled e consultar control.check() em pontos seguros.

O runtime não cria threads para matar uma função bloqueante. Portanto, um adaptador legado que ignora o token não pode ser interrompido no meio da chamada; o runtime identifica cancelamento/timeout quando o controle volta a ser observado e descarta o resultado tardio. I/O e backends com cancelamento nativo devem conectar seu mecanismo de abort ao token em uma etapa de integração específica.

## Leases e back-pressure

ExecutionLeaseManager recebe capacidade máxima por dimensão do ResourceVector, máximo de tarefas ativas e máximo de tarefas aguardando admissão.

Acquire só concede um lease quando há vaga de concorrência e a soma das reservas cabe na capacidade configurada. A fila de espera é limitada; quando cheia, retorna QueueFull sem admitir trabalho adicional. Cancelamento e deadline também são verificados durante a espera.

ExecutionLease é RAII: ao sair do escopo, o lease devolve as reservas ao gerenciador e acorda tarefas em espera. A capacidade e os limites são compartilhados entre execuções que usam a mesma instância do gerenciador. O código não promete justiça FIFO entre waiters.

## Execução do plano

CognitiveRuntime.execute_with_control mantém a execução dos componentes de um mesmo plano sequencial. O paralelismo permitido nesta versão é entre tarefas independentes que compartilham um ExecutionLeaseManager; isso não transforma dependências entre etapas em execução paralela. Cada componente adquire um lease sobre seu custo estimado e libera a reserva após terminar.

O método execute existente continua disponível e cria um gerenciador privado com concorrência 1, preservando o comportamento anterior.

## Limites conhecidos

- Os recursos são estimativas e reservas lógicas, não quotas de cgroups, limites de memória ou controle de GPU.
- A fila limita a quantidade de tarefas esperando, não implementa prioridade nem garantia FIFO.
- Adaptadores legados sem polling não são interrompidos dentro da chamada.
- RuntimeHost JSONL v2 permanece síncrono; protocolo e cliente Python não expõem cancelamento por tarefa nem multiplexação.
- MainWindow/Ollama ainda não usam estas primitives; a integração da aplicação é o próximo incremento.
- O adaptador llama.cpp não está incluído; será adicionado somente com ciclo de vida, detecção de runtime e testes próprios.
- Esta etapa não implementa streaming, prefetch, offload ou treinamento de modelos.
