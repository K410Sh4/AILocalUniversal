# K.IA — Persistent Cognitive Memory & Semantic Integration v0.4

## Escopo

A K.IA 0.4 adiciona memória operacional durável e integra o catálogo NeSA ao caminho de recuperação já existente. Não é memória paramétrica: pesos de LLM, LoRA, adaptadores e parâmetros de modelos não são alterados.

## Ciclo de persistência

1. O processo Python inicia `kia-runtime-host` com protocolo JSONL v2.
2. Antes do primeiro `replace_state`, o cliente consulta o snapshot SQLite local.
3. Se houver snapshot, envia `restore_learning`; Rust valida a rede com `AdaptiveCognitiveNetwork.validate()`.
4. Python envia o estado operacional atual. Rust aplica `carry_learning_from`, preservando somente conexões com identidade tipada compatível.
5. Após a sincronização, Python solicita `export_network` e grava o snapshot/evento em uma transação SQLite.
6. Após feedback independente, a rede é exportada e persistida novamente como `feedback_applied`.

HardwareSnapshot, ResourceBudget e IDs de executores nunca são restaurados: RAM/GPU, disponibilidade e adaptadores mudam entre sessões.

## Armazenamento

Padrão:

```text
$XDG_DATA_HOME/ailocal-universal/kia/cognitive-memory.sqlite3
```

Fallback:

```text
~/.local/share/ailocal-universal/kia/cognitive-memory.sqlite3
```

Permissões: diretório `ailocal-universal` 0700, subdiretório `kia` 0700, arquivo SQLite 0600. O banco usa transação `BEGIN IMMEDIATE`, `synchronous=FULL`, journal DELETE e `PRAGMA user_version=1`.

Tabelas:
- `cognitive_snapshots`: uma rede atual por namespace, versão de esquema/rede, hash e JSON canônico;
- `cognitive_events`: sequência append-only com event_id, tipo, versão e metadados agregados; limite de 10.000 eventos por namespace.

O snapshot é protegido por SHA-256 e a restauração só ocorre após verificar o hash e o contrato básico Python; a validação completa dos nós e das relações é feita no Rust antes da aplicação. Notas livres de CognitiveFeedback são substituídas por null antes da serialização, preservando outcome, validation_ref, pesos e contadores. O banco não é criptografado. As permissões protegem contra outros usuários locais sem acesso, não contra comprometimento da mesma conta, root ou malware.

Campos típicos proibidos no snapshot: prompts, raw_prompt, user_input, input_payload, conversation, messages, document_text e raw_content. A entrada da solicitação Rust mantém apenas task_id. Eventos persistidos guardam contagens, versão e hash, não texto da conversa.

## Plasticidade persistente

A plasticidade desta versão é operacional: peso e contadores das conexões capability→component. O histórico de feedback permanece ligado à rede e limitado a 4.096 entradas quando o estado é reconciliado. Feedback só é enviado quando uma saída determinística foi reproduzida e validada com referência independente. Saídas de LLM não fortalecem rotas automaticamente.

Snapshots incompatíveis ou corrompidos bloqueiam a restauração; a aplicação utiliza seu fallback normal em vez de confiar em dados não validados.

## NeSA + Knowledge progressivo

Com Knowledge habilitado:
- planner Rust recebe `memory-knowledge-library` (kind `memory`) como executor disponível;
- o pedido exige `retrieval` e `generation`, garantindo que a recuperação tenha também um modelo para síntese;
- KnowledgeRetrievalWorker consulta NeSA FTS5 para obter candidatos de página/documento;
- HybridRetriever procura chunks dentro desses documentos;
- se o limite de resultados não for preenchido, a busca expande globalmente e deduplica por chunk_id;
- ContextComposer continua anexando somente chunks originais, com IDs [E#], origem, hash e localização.

Fichas de página, resumos extrativos e seus scores são sinais de navegação, não evidência factual e não são inseridos como texto no prompt. O Cognitive Inspector registra IDs e contagens de candidatos.

Com Knowledge desativado, o provedor não é publicado no grafo e nenhum estágio de recuperação é acionado por esta integração.

## Limites da 0.4

- Um namespace local; sem replicação, sincronização multi-dispositivo ou controle de conflito entre cópias do banco.
- Sem criptografia em repouso própria.
- Retenção limitada do event log (10.000) e do histórico de feedback da rede (4.096).
- NeSA ainda usa FTS5 lexical para páginas; não há embeddings de páginas, ANN, reranker ou relações factuais tipadas.
- O custo do provedor Knowledge é uma reserva inicial explícita e ainda não calibrada por benchmark.
- A aceitação operacional no Arch Linux e testes com a base real de documentos permanecem necessários.
