# NeuralMap — editor visual e runtime de workflows

**Estado:** primeira implementação em desenvolvimento na branch `feature/neuralmap-v1`. Esta documentação distingue o que já está codificado do que ainda exige backend, teste real ou refinamento.

O NeuralMap permite desenhar um fluxo de processamento por nós especializados. O formato do grafo é declarativo e não transporta código executável.

## 1. Arquitetura

O subsistema fica separado do `core.Orchestrator` sequencial existente:

- `workflows/graph.py`: modelo tipado, portas, serialização e validação estática.
- `workflows/runtime.py`: executor assíncrono independente da interface, com condições de aresta, trace, cancelamento e loop limitado.
- `workflows/handlers.py`: handlers que fazem ponte para engines registradas; inclui Ollama para código, conversa e revisão, além de um contrato opcional de imagem.
- `workflows/package_io.py`: leitura/atualização segura de `.neuralinjector`, manifestos, checksums e referência ao grafo.
- `app/views/neuralmap_view.py`: editor PySide6 baseado em `QGraphicsScene`.
- `workers/neuralmap_worker.py`: execução em QThread, sem bloquear a interface.

Essa divisão permite validar e executar um grafo sem abrir o canvas. O editor não contém a lógica de inferência e o runtime não importa widgets Qt.

## 2. Formato do arquivo

O identificador é `ailocal.pipeline-graph`, versão `1.0`.

Arquivo recomendado dentro do pacote:

```text
graph/pipeline.graph.json
```

O formato contém:

- `id`, `name`, `description`: identidade do mapa.
- `nodes`: nós tipados e suas configurações.
- `edges`: conexões direcionadas com portas de origem e destino.
- `metadata`: metadados opcionais do grafo.
- `ui.position` e `ui.color`: metadados visuais; não alteram execução.

Schema: [pipeline-graph.schema.json](../schemas/pipeline-graph.schema.json).

O grafo referencia engine/model IDs e NeuralPlugins; não incorpora pesos dos modelos. O manifesto NIP precisa declarar referências de modelos em `compatibility.models`, engines em `compatibility.engines` e plugins em `components.plugins`. Ao salvar no pacote, referências não declaradas causam recusa com reason_code estável.

## 3. Tipos de nós v1

| Tipo | Função |
|---|---|
| `input.text` | Recebe o texto inicial do usuário. |
| `input.attachment` | Recebe referências a anexos entregues ao runtime. |
| `specialist.code` | Gera ou revisa código usando engine registrada. |
| `specialist.chat` | Explica a solução e sintetiza contexto. |
| `specialist.image` | Encaminha prompt a um adaptador de imagem registrado. |
| `specialist.review` | Emite decisão estruturada: aprovação, nota, feedback e IDs para retry. |
| `control.loop` | Limita as revisões; v1 permite um controlador por grafo. |
| `filter.context` | Limita conteúdo/contexto antes dos especialistas. |
| `hardware.profile` | Reutiliza o Adaptive Resource Planner e retorna ResourceBudget/relatório. |
| `merge.outputs` | Consolida código, explicação, imagem e revisão. |
| `output.response` | Produz o objeto de resposta final. |
| `output.trace` | Expõe referência ao trace de execução. |

Nós especialistas declaram engine, model_id, system prompt, referência opcional de NeuralPlugin, parâmetros de geração, uso de ResourceBudget e se a falha é opcional.

## 4. Conexões e condições

Cada aresta é dirigida e aponta para portas nomeadas:

- `always`: percorrida quando o nó de origem produziu a porta.
- `on_success`: percorrida quando o resultado da origem é considerado bem-sucedido.
- `on_failure`: percorrida quando o resultado da origem é considerado falha/recusa/revisão negativa.

O validador rejeita portas inexistentes, referências a nós ausentes, IDs duplicados, tipos desconhecidos, ciclos não controlados e grafos sem caminho entre entrada e saída.

Loops só são aceitos quando a aresta de retorno sai de `control.loop.repeat` e chega à porta `feedback` de um especialista. Na v1, há um único `specialist.review` associado a um único `control.loop`.

## 5. Ciclo de revisão

O template de referência usa:

```text
input.text → filter.context
                   ├→ specialist.code ──────┐
                   ├→ specialist.chat ← code ├→ specialist.image
                   └─────────────────────────┘
code + explanation + image → specialist.review
       ├─ on_success → merge.outputs → output.response
       └─ on_failure → control.loop
                            ├─ repeat → especialistas selecionados
                            └─ limite → merge.outputs → output.response
```

O revisor deve retornar JSON com:

```json
{
  "approved": false,
  "score": 0.72,
  "notes": "A explicação não corresponde ao código.",
  "feedback": "Corrija os pontos indicados.",
  "retry_targets": ["code", "chat"]
}
```

`retry_targets` contém IDs de nós conectados a `control.loop.repeat`. O runtime invalida as saídas dos nós que serão refeitos, executa o alvo e seus dependentes, e repete a revisão até aprovação ou o máximo configurado (1–20; template usa 3).

Ao atingir o limite, escolhe o bundle com maior `score` visto até então e marca `convergence: "limit_reached"` e `Revisão não convergente` no trace/resultado. A nota é uma métrica declarada pelo revisor, não uma probabilidade calibrada.

## 6. Execução e backends

### Dry-run

O botão **Executar · dry-run** não chama handlers, serviços de rede ou modelos. Ele simula os especialistas com saídas marcadas como DRY-RUN, testa conexões, loop e estrutura do output. A imagem é apenas um placeholder com `status: "not_generated"`.

### Execução real

O botão **Executar real** pede uma entrada e inicia a execução em QThread. O runtime atual registra handlers Ollama para código, explicação e revisão, reaproveitando o EngineAdapter existente. Parâmetros de contexto e threads são limitados pelo ResourceBudget quando o nó recebe orçamento.

O revisor usa resposta JSON solicitada pela API Ollama. O parser valida a estrutura antes de aceitar a decisão.

### Imagem / Flux

A v1 define `ImageGenerationAdapter`, mas ainda não registra automaticamente um backend Flux. Sem adaptador de imagem instalado, o nó do template é opcional e falha sem abortar o mapa; o resultado contém `image: null` e o trace marca `optional_failed`.

Assim, o dry-run e a infraestrutura do grafo existem, mas **o critério de aceite de gerar uma imagem real com Flux ainda não está atendido**. Para isso é necessário instalar/integrar um backend de imagem e validar criação de artefatos reais.

## 7. Output final

O `output.response` produz um dicionário estruturado com:

- `code`: texto do código.
- `explanation`: explicação.
- `image`: referência estruturada ao artefato ou `null` quando não gerado.
- `review`: `approved`, `score`, `notes`, `iterations`, `convergence`.
- `trace_id` e `generated_at`.

A aba NeuralMap mostra atualmente JSON de resultado e eventos do trace. A renderização integrada no ChatView com syntax highlight, Markdown rico e preview de imagem permanece pendente.

## 8. Editor visual

A aba **NeuralMap** fornece:

- Biblioteca de tipos com arrastar/soltar ou duplo clique.
- Canvas amplo com grade, zoom e pan com botão do meio.
- Nós arrastáveis e portas nomeadas.
- Conexões com tipo `always`, `on_success` ou `on_failure`.
- Painel de propriedades por JSON, incluindo rótulo, habilitação e configuração.
- Validação, template, salvar/abrir JSON e salvar no pacote.
- Undo/redo por snapshots.
- Abas de resultado e trace.
- Worker QThread e solicitação de cancelamento cooperativo.
- Remoção de nós/conexões selecionados via Delete/Backspace.
- Realce visual de nós em execução, concluídos e com falha.
- Smoke test PySide6 offscreen cobrindo abertura do editor, template, canvas, conexões e undo/redo.

A v1 prioriza clareza do grafo e contratos explícitos; ainda não implementa subgrafos, colaboração multiusuário ou layout automático.

## 9. Persistência em .neuralinjector

O helper `save_graph_to_package()`:

1. Lê o ZIP/ZIP64 sem extrair para o filesystem.
2. Rejeita traversal, caminhos absolutos, backslashes, duplicatas, symlinks e arquivos acima dos limites configurados.
3. Verifica os SHA-256 existentes.
4. Confere se os modelos, engines e plugins usados pelo grafo estão declarados no manifesto.
5. Atualiza `components.pipelines` e adiciona `graph/pipeline.graph.json`.
6. Recalcula checksums e grava pacote temporário, substituindo o original atomicamente.

Pacotes que declaram assinatura Ed25519 são recusados para leitura/edição nesta versão porque ainda não existe verificação de assinatura com chave confiável. O v1 não oferece assinatura com uma chave de autoria; use um pacote sem assinatura até essa capacidade existir. Nenhum script arbitrário é executado ao abrir, validar ou salvar um mapa.

## 10. Segurança

- Apenas tipos de nó constantes e handlers explicitamente registrados podem executar.
- O grafo não aceita nomes de classe, código Python, shell ou scripts arbitrários.
- Os especialistas recebem uma instrução de segurança central que plugins/grafo não podem substituir.
- Saídas de imagem devem referenciar um artefato por identificador/caminho relativo; base64 inline e caminhos absolutos/traversal são rejeitados.
- Requisitos obrigatórios de hardware são verificados pelo planejador.
- Saídas e prompts de outros nós são tratados como dados não confiáveis.
- Os pacotes são verificados por checksums; checksum não é prova de autoria. Assinaturas verificáveis serão uma etapa futura.

## 11. Como experimentar

1. Abra a aba **NeuralMap**.
2. Clique em **Aplicar template**.
3. Confirme as configurações de modelos/engine nos nós especialistas.
4. Clique em **Validar**.
5. Execute **dry-run** para testar a estrutura sem chamar modelos.
6. Salve JSON ou selecione um pacote `.neuralinjector` em **Salvar no pacote**.
7. Para execução real, garanta Ollama e os modelos declarados. A imagem só será gerada quando um adaptador compatível estiver registrado.

O pacote de exemplo declara os modelos e engines do template em `examples/neuralinjector/manifest.example.json` e inclui uma cópia em `examples/neuralinjector/graph/pipeline.graph.json`.

## 12. Limitações e próximos passos

- Integrar um backend de imagem real (Flux ou outro) e armazenamento de artefatos.
- Integrar anexos à UI e ao contexto dos especialistas.
- Expandir execução paralela de nós independentes com orçamento/limites e sem quebrar determinismo.
- Adicionar validação automática JSON Schema no runtime/loader.
- Renderizar o objeto final na aba Chat com blocos de código, Markdown e imagem.
- Validar manualmente a interface em sessão gráfica Linux/Arch e executar o fluxo com Ollama real; benchmarks e latência em hardware-alvo permanecem pendentes.

**Validação automatizada:** GitHub Actions no commit `d56e37e` — Ruff aprovado e 113 testes passaram, incluindo o smoke test PySide6 offscreen.

## Licenciamento do NeuralMap

O código original do editor, modelo de grafo, runtime, handlers, validação, schemas e integração com pacotes integra o escopo proprietário do AILocal Universal. Isso não transfere ao projeto a titularidade de workflows criados por usuários, documentos referenciados, modelos, adaptadores ou ativos de terceiros. Cada grafo exportado e cada conteúdo referenciado deve respeitar a licença do respectivo criador ou fornecedor.
