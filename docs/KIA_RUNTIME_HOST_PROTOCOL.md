# K.IA Runtime Host — JSONL Protocol v1

## Transporte

- Processo local persistente: `kia-runtime-host`.
- Entrada: uma mensagem JSON UTF-8 por linha (newline-delimited JSON).
- Saída: exatamente uma resposta JSON por solicitação, também delimitada por newline.
- O stdout é reservado ao protocolo. Logs/debug devem usar stderr.
- Limite de entrada por mensagem: 4 MiB.
- A aplicação inicia o processo sem shell, mantém stdin/stdout abertos e encerra com `shutdown` ou EOF.
- Cada mensagem exige `protocol_version=1` e um `request_id` ASCII estável.
- O host não persiste payloads e não registra prompts nem documentos.

## Envelope de solicitação

```json
{
  "protocol_version": 1,
  "request_id": "req-0001",
  "command": { "type": "health" }
}
```

As variantes de `command.type` são:

- `health`: versão do host, protocolo e versão de schema dos contratos.
- `replace_state`: substitui atomicamente a visão em memória do grafo, snapshot, budget e IDs de executores disponíveis.
- `plan`: recebe um CognitiveRequest e devolve ExecutionPlan.
- `record_feedback`: registra feedback avaliado e atualiza a prioridade da conexão.
- `inspect`: devolve contagens, IDs, versão, budget e executores.
- `shutdown`: responde e encerra o processo.

Comandos com payload usam `command.payload`, por exemplo:

```json
{
  "protocol_version": 1,
  "request_id": "plan-1",
  "command": {
    "type": "plan",
    "payload": {
      "request": {
        "schema_version": 1,
        "request_id": "task-1",
        "intent": "calculation",
        "context_tags": ["cost_estimate"],
        "required_capabilities": ["mathematics"],
        "input": {"units": 250, "unit_cost": 12.5},
        "max_components": 3
      }
    }
  }
}
```

## Envelope de resposta

Sucesso:

```json
{
  "protocol_version": 1,
  "request_id": "plan-1",
  "ok": true,
  "result": {
    "request_id": "task-1",
    "network_version": 4,
    "selections": [],
    "reserved_resources": {}
  }
}
```

Falha:

```json
{
  "protocol_version": 1,
  "request_id": "plan-1",
  "ok": false,
  "error": {
    "code": "planning_failed",
    "message": "..."
  }
}
```

## Segurança e semântica

- O host aceita apenas comandos declarados; nunca executa texto, comandos de shell ou código fornecidos no payload.
- `replace_state` valida IDs, referências do grafo, budget e se os executores referenciados existem e estão habilitados.
- `available_executors` significa que o lado da aplicação possui um adaptador para o ID; o host Rust apenas planeja nesta versão.
- `plan` não executa inferência. A aplicação Python continua responsável por chamar ferramentas e motores que correspondam às seleções.
- O payload `input` só atravessa a ponte para validar/planejar; não é copiado para logs, resposta do plano ou telemetria.
- A resposta inclui o request_id e a versão do protocolo para impedir associação cruzada de respostas.
- As chamadas do cliente Python são serializadas por lock; uma instância do cliente mantém um único processo e uma sequência de requisições.
- O encerramento usa `shutdown`; a aplicação também encerra o processo em caso de falha de comunicação.

## Limites da v1

O host é síncrono e atende uma solicitação por vez. Não há execução concorrente, streaming de token, filas, timeout por componente, leases, transporte de payload binário ou conexão de rede. O protocolo é IPC local e não deve ser exposto como endpoint TCP sem autenticação e autorização adicionais.
