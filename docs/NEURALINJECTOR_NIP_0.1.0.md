# NeuralInjector Package Specification (NIP) 0.1.0

**Status:** proposta inicial para revisão  
**Projeto:** AILocal Universal  
**Extensão oficial:** `.neuralinjector`  
**Gerenciador:** NeuralPlugin Manager  
**Motor:** NeuralInjector Engine

## 1. Resumo

A NeuralInjector Package Specification (NIP) define um contêiner portátil para transportar plugins de especialização e otimização de modelos locais. Um pacote pode reunir regras, adaptadores neurais, perfis de hardware, transformações estruturais, pipelines, gramáticas e avaliações.

O pacote é independente dos pesos completos do modelo-base, mas pode depender de um modelo previamente instalado. Essa independência não significa compatibilidade universal: o manifesto deve declarar modelos, arquiteturas, digests e capacidades de runtime necessários.

A NIP 0.1.0 é uma especificação documental proposta. Ela não afirma que já existe um leitor, instalador ou runtime funcional.

## 2. Identidade e nomes

| Item | Valor normativo |
|---|---|
| Nome do formato | NeuralInjector Package |
| Extensão | `.neuralinjector` |
| Identificador do formato | `ailocal.neuralinjector` |
| Versão desta especificação | `0.1.0` |
| Manifesto obrigatório | `manifest.json` |
| Gerenciador | NeuralPlugin Manager |
| Motor de aplicação | NeuralInjector Engine |

A extensão `.ailu` não será usada para este formato.

## 3. Contêiner

Na versão 0.1.0, o pacote será um arquivo ZIP compatível com ZIP64, usando a extensão `.neuralinjector`.

Regras:

- O arquivo deve conter um manifesto na raiz chamado `manifest.json`.
- O manifesto deve ser JSON UTF-8, sem BOM.
- Os caminhos internos devem ser relativos, normalizados e usar barra / como separador.
- Nomes de caminhos são sensíveis a maiúsculas/minúsculas para fins de identificação.
- O pacote não pode conter caminhos absolutos, segmentos `..`, links simbólicos ou entradas que escapem do diretório de extração.
- A ordem e a presença dos componentes são determinadas pelo manifesto.
- Arquivos desconhecidos podem ser preservados por ferramentas de inspeção, mas não podem ser executados nem aplicados automaticamente.

Estrutura de referência:

~~~text
example.neuralinjector
├── manifest.json
├── plugins/
│   └── <plugin-id>/
│       ├── plugin.json
│       └── rules/
│           └── system.md
├── neural/
│   ├── adapters/
│   │   └── adapter.safetensors
│   └── transformations/
│       ├── pruning/
│       └── restoration/
├── hardware/
│   └── profiles/
├── pipelines/
├── grammars/
├── evaluations/
└── security/
    ├── checksums.sha256
    └── signature.ed25519
~~~

Os diretórios são opcionais quando não houver componentes daquele tipo. O manifesto e o arquivo de checksums são obrigatórios. A assinatura é opcional na versão 0.1.0.

## 4. Manifesto

O manifesto descreve identidade, compatibilidade, componentes e integridade.

Campos obrigatórios:

### 4.1 format

Deve ser exatamente `ailocal.neuralinjector`.

### 4.2 format_version

Versão da especificação NIP usada pelo pacote. Nesta proposta, o valor é `0.1.0`.

A versão do formato é independente da versão comercial/técnica do pacote.

### 4.3 package

Metadados do pacote:

- `id`: identificador estável e globalmente único, em formato reverse-DNS recomendado.
- `name`: nome legível.
- `version`: versão do pacote em SemVer.
- `kind`: specialization, optimization, adapter_bundle ou workflow.
- `description`: descrição opcional.
- `authors`: autores ou mantenedores.
- `license`: licença declarada.
- `homepage`: endereço informativo opcional.

### 4.4 compatibility

Declara modelos, arquiteturas, backends e plataformas.

Para cada modelo:

- `family`: família declarada.
- `architecture`: arquitetura esperada.
- `model_id`: nome/tag informativo do modelo.
- `digest`: hash imutável do modelo-base, quando conhecido.
- `match_policy`: exact_digest ou architecture_compatible.

Regras:

- Adaptadores de pesos devem usar identidade estrita e digest do modelo-base sempre que o backend permitir.
- Compatibilidade apenas por arquitetura é aceitável para regras textuais e componentes que não alterem pesos.
- O nome/tag do modelo, isoladamente, não prova identidade.
- Um backend precisa declarar as features requeridas antes de aplicar um componente.

### 4.5 components

Lista os artefatos do pacote:

- `plugins`: manifestos de NeuralPlugins.
- `adapters`: adaptadores e formatos de pesos.
- `transformations`: operações estruturais.
- `hardware_profiles`: perfis de execução.
- `pipelines`: fluxos declarativos.
- `grammars`: gramáticas de saída.
- `evaluations`: casos de teste e avaliações.

Todos os caminhos são relativos à raiz do pacote.

### 4.6 integrity

Deve declarar o algoritmo SHA-256 e o caminho de `security/checksums.sha256`.

O arquivo de checksums deve listar os arquivos do pacote, exceto ele próprio e a assinatura. A assinatura opcional cobre uma representação canônica do manifesto e o conteúdo do arquivo de checksums. O processo de canonicalização e assinatura deverá ser normatizado antes de declarar suporte criptográfico interoperável.

Um checksum detecta alteração de conteúdo em relação ao valor esperado; sozinho, não prova quem criou o pacote. A autenticidade depende de assinatura verificada com chave confiável.

## 5. Tipos de componentes

### 5.1 Regras e prompts

Arquivos Markdown ou JSON podem declarar regras de sistema, comportamento, saída e exemplos. A compactação do contêiner reduz o tamanho armazenado; só a condensação efetiva do texto reduz tokens de prompt.

Quando houver uma versão condensada, o pacote deve preservar a versão de origem e associar avaliações que verifiquem se os requisitos comportamentais foram mantidos. O consumidor pode escolher a variante após avaliação.

### 5.2 Adaptadores neurais

A versão 0.1.0 prevê metadados para adaptadores como LoRA e DoRA em formatos como Safetensors ou GGUF, desde que o backend declare suporte real ao formato e ao método.

A NIP não define um formato de tensor novo. Pesos completos do modelo-base não são incluídos por padrão.

### 5.3 Quantização

Um perfil pode recomendar quantização, precisão ou offloading. Para aplicar uma mudança real nos pesos, deve existir um artefato convertido ou uma transformação suportada pelo motor.

Uma recomendação como “4-bit” não transforma um modelo FP16/FP32 apenas por aparecer no manifesto.

### 5.4 Poda e transformações estruturais

Transformações devem declarar:

- Arquitetura e identidade do modelo-base.
- Operação e versão da transformação.
- Tensores, camadas, cabeças ou estruturas afetadas.
- Shapes e pré-condições esperadas.
- Artefatos adicionais necessários.
- Features obrigatórias do runtime.
- Se a transformação é obrigatória ou opcional.

Máscaras que não reduzem o trabalho dos kernels podem não produzir aceleração. O runtime precisa oferecer suporte a execução esparsa ou a uma estrutura fisicamente reduzida.

### 5.5 Restauração

O termo restauração significa reconstruir estruturas ou pesos removidos/alterados somente quando houver dados suficientes e compatibilidade exata.

O pacote pode conter deltas, tensores preservados ou referências criptograficamente identificadas ao modelo-base. Uma instrução genérica para “reativar neurônios” não é suficiente para reconstrução.

### 5.6 Perfis de hardware

Um perfil pode declarar orçamento de RAM/VRAM, contexto alvo, backend preferido e parâmetros permitidos. Perfis são candidatos; a seleção final exige detecção de hardware, verificação de suporte e, quando possível, benchmark local.

O perfil não pode presumir que o hardware de destino seja igual ao computador em que o pacote foi criado.

### 5.7 Pipelines e ferramentas

A versão 0.1.0 aceita apenas declarações de pipelines e ações reconhecidas pelo AILocal Universal. Scripts arbitrários não devem ser executados durante importação ou ativação. Qualquer futura extensão executável exigirá especificação de permissões, sandbox, assinatura e consentimento explícito.

## 6. Seleção adaptativa de hardware

O NeuralInjector Engine deverá:

1. Detectar recursos relevantes do computador de destino.
2. Filtrar perfis cujos requisitos não possam ser atendidos.
3. Verificar as capacidades reais do backend.
4. Escolher uma estratégia conforme limites e objetivos declarados.
5. Executar benchmark local quando disponível.
6. Registrar a configuração escolhida e seus resultados.

Métricas recomendadas:

- Tempo até o primeiro token (TTFT).
- Tokens por segundo.
- Latência total.
- Tempo de carregamento.
- Pico de RAM e VRAM.
- Contexto utilizado.
- Qualidade em conjunto de avaliação.
- Estado frio/quente e versão do backend.

**Não existe garantia de mesma velocidade absoluta em computadores diferentes.** CPU, largura de banda de memória, RAM, VRAM, GPU, drivers, kernels e temperatura impõem limites físicos. A promessa possível é selecionar e documentar o melhor perfil validado para o hardware disponível.

Nenhum ganho deve ser declarado sem benchmark reproduzível e avaliação de qualidade.

## 7. Dependências e composição

Plugins podem depender de outros plugins por identificador e faixa de versão. Dependências cíclicas devem ser rejeitadas.

Conflitos entre plugins precisam ser apresentados antes da ativação. A ordem de importação não pode mudar silenciosamente o comportamento final.

O manager deve construir uma composição determinística, registrar a origem de cada regra e permitir que o usuário desative componentes individualmente.

## 8. Instalação transacional

Fluxo proposto:

1. Abrir o contêiner em modo seguro.
2. Validar manifesto e esquema.
3. Verificar limites de descompactação.
4. Verificar caminhos e entradas ZIP.
5. Validar checksums e assinatura, quando houver.
6. Resolver dependências e compatibilidade.
7. Mostrar prévia e permissões solicitadas.
8. Extrair para uma área temporária.
9. Ativar componentes aprovados.
10. Registrar estado e permitir rollback.

Falha em componente obrigatório deve impedir a ativação do pacote. Falha em componente opcional deve aparecer no relatório.

## 9. Segurança

Importar um pacote não equivale a confiar nele.

Requisitos mínimos:

- Proteção contra ZIP Slip e traversal.
- Limites para compressão expansiva e quantidade de entradas.
- Rejeição de links simbólicos e caminhos duplicados ambíguos.
- Verificação de SHA-256.
- Verificação opcional de Ed25519 com chave confiável.
- Nenhuma execução automática de scripts.
- Permissões explícitas para acesso a rede, arquivos e ferramentas.
- Instalação em diretório controlado e rollback.
- Licença e origem dos pesos/adaptadores declaradas.
- Não armazenar segredos no pacote.

## 10. Versionamento

- `format_version`: versão do contrato NIP.
- `package.version`: versão independente do pacote.
- Versões major da NIP podem introduzir incompatibilidades.
- Atualizações minor adicionam recursos compatíveis.
- Correções patch não alteram o significado do contrato.

Um consumidor deve rejeitar versões major desconhecidas e não deve reinterpretar silenciosamente campos desconhecidos como operações executáveis.

## 11. Exemplo e esquema

- Manifesto de exemplo: [examples/neuralinjector/manifest.example.json](../examples/neuralinjector/manifest.example.json)
- JSON Schema: [schemas/neuralinjector-manifest.schema.json](../schemas/neuralinjector-manifest.schema.json)
- Gerenciador: [NEURALPLUGIN.md](NEURALPLUGIN.md)

O manifesto de exemplo é ilustrativo. Ele não é, isoladamente, um arquivo `.neuralinjector` pronto para instalação; para formar um pacote, todos os artefatos referenciados precisam existir e o arquivo de checksums precisa ser gerado sobre os arquivos finais.

## 12. Critérios para considerar a NIP 0.1.0 implementada

- Validador de manifesto e JSON Schema.
- Leitor ZIP64 com limites e proteção contra traversal.
- Verificador de checksums.
- Inspeção de compatibilidade de modelo/backend.
- Importação em modo dry-run.
- Instalação transacional e rollback.
- Testes negativos de arquivos malformados e maliciosos.
- Testes de compatibilidade e benchmarks.
- Documentação de limitações por backend.

Até que esses critérios sejam atendidos, a NIP 0.1.0 permanece uma proposta de especificação, não uma tecnologia já implementada.
