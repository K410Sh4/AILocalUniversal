# NeuralPlugin Manager

**Status:** proposta arquitetural  
**Projeto:** AILocal Universal  
**Formato de pacote:** NeuralInjector Package  
**Extensão:** `.neuralinjector`  
**Especificação associada:** NIP 0.1.0

## 1. Objetivo

O **NeuralPlugin Manager** será o subsistema do AILocal Universal responsável por descobrir, importar, validar, instalar, habilitar, desabilitar, atualizar, remover, combinar e exportar plugins de especialização e otimização para modelos locais.

Um NeuralPlugin não será limitado a um prompt de sistema. Ele poderá declarar regras, adaptadores de pesos, perfis de hardware, transformações estruturais, pipelines, gramáticas e avaliações. Os componentes serão opcionais e dependerão das capacidades do modelo e do motor de inferência.

O manager administra plugins; o pacote portátil que os transporta é um arquivo **.neuralinjector**; e o **NeuralInjector Engine** interpreta o pacote e coordena a aplicação dos componentes compatíveis.

## 2. Terminologia oficial

| Termo | Responsabilidade |
|---|---|
| **NeuralPlugin** | Unidade modular de comportamento, especialização ou otimização |
| **NeuralPlugin Manager** | Gerenciador integrado ao AILocal Universal |
| **NeuralInjector Package** | Pacote portátil que pode conter um ou vários NeuralPlugins |
| **.neuralinjector** | Extensão oficial do pacote |
| **NeuralInjector Engine** | Valida compatibilidade e coordena a aplicação dos componentes |
| **NIP** | NeuralInjector Package Specification |

A extensão anterior `.ailu` não faz parte deste padrão. A extensão oficial é exclusivamente `.neuralinjector`.

## 3. Tipos de plugin

### 3.1 Rules Plugin

Contém instruções e políticas declarativas para compor o contexto de sistema de um modelo:

- Instruções de sistema e comportamento.
- Idioma, tom e formato de saída.
- Restrições de domínio e critérios de resposta.
- Exemplos few-shot.
- Regras de prioridade e composição.

As regras são texto/configuração, não alterações nos pesos. Compactação ZIP reduz o tamanho armazenado, mas não reduz por si só a quantidade de tokens enviada ao modelo. Uma versão semanticamente condensada só poderá substituir a original após avaliação de equivalência comportamental.

### 3.2 Neural Adapter Plugin

Contém adaptadores como LoRA ou DoRA e seus metadados de compatibilidade. O carregamento depende de suporte explícito do backend, da arquitetura e do modelo-base.

Para adaptadores de pesos, a compatibilidade deve ser estrita. Sempre que disponível, o digest imutável do modelo-base será obrigatório. Não se deve presumir que adaptadores treinados para modelos apenas da mesma família sejam intercambiáveis.

### 3.3 Optimization Plugin

Declara perfis de execução, como orçamento de memória, contexto alvo, parâmetros de batch, número de threads e opções de backend. Valores são recomendações condicionadas às capacidades reconhecidas pelo runtime.

Uma configuração declarativa não converte automaticamente os pesos. Uma otimização de quantização que exija pesos quantizados deve apontar para o artefato quantizado correspondente ou para uma transformação realmente implementada e validada.

### 3.4 Neural Structure Plugin

Declara transformações estruturais, como poda estruturada, máscaras suportadas pelo runtime e artefatos de restauração de tensores/deltas.

O termo “restauração neural” não significa que qualquer neurônio possa ser religado universalmente. A restauração só será permitida quando o pacote identificar a arquitetura, os tensores, os shapes, o modelo-base e os dados necessários para reconstrução. Transformações sem suporte explícito devem ser recusadas ou marcadas como não aplicadas; nunca devem ser ignoradas silenciosamente.

### 3.5 Workflow Plugin

Contém pipelines declarativos, gramáticas, templates e referências a ferramentas conhecidas pelo AILocal Universal. Na NIP 0.1.0, o formato não autoriza execução automática de scripts arbitrários.

### 3.6 Knowledge Plugin

Pode declarar fontes, documentos, metadados e parâmetros de ingestão/recuperação. Índices vetoriais específicos de um backend devem declarar o formato e as dependências; quando não forem portáveis, o pacote deve transportar os documentos/fontes necessários para reconstrução ou indicar claramente a dependência externa.

## 4. Experiência na interface

O IA Hub deverá oferecer uma aba **NeuralPlugin** dentro de Configurações.

Operações previstas:

1. Importar arquivo `.neuralinjector`.
2. Validar estrutura, hashes, assinatura e compatibilidade antes da instalação.
3. Mostrar nome, versão, autor, licença, dependências e componentes do pacote.
4. Exibir modelos e backends compatíveis.
5. Habilitar/desabilitar cada plugin individualmente.
6. Associar plugins a um ou mais modelos.
7. Definir prioridades e resolver conflitos de regras.
8. Consultar quais componentes foram aplicados, ignorados ou recusados e por quê.
9. Exportar plugins selecionados em um novo pacote.
10. Atualizar, remover e reverter instalações.

A importação deve oferecer uma prévia (dry run) antes de alterar a configuração ativa. A instalação deve ser transacional, com rollback em caso de falha.

## 5. Composição das regras

As regras devem ser compostas de forma determinística e rastreável.

Ordem conceitual:

1. Regras internas de segurança e limites da aplicação.
2. Regras globais escolhidas pelo usuário.
3. Regras específicas do modelo.
4. NeuralPlugins habilitados, respeitando prioridade e dependências.
5. Instrução da conversa, quando explicitamente permitida pela política do aplicativo.

Essa ordem é uma proposta de composição do software, não uma garantia de que o modelo obedecerá a todas as instruções. Plugins não podem enfraquecer as regras de segurança da aplicação.

Cada plugin deve declarar a estratégia de composição. Conflitos entre valores exclusivos precisam ser reportados ao usuário; não devem ser resolvidos silenciosamente apenas pela ordem de importação. O IA Hub deve registrar a origem das instruções que compõem o prompt final.

## 6. Compatibilidade e aplicação

O NeuralInjector Engine consulta um registro de capacidades do backend. A aplicação de cada componente depende de:

- Arquitetura e identidade do modelo-base.
- Digest do modelo, quando necessário.
- Versão do backend e recursos expostos.
- Formato e versão do artefato.
- Plataforma e recursos de hardware.
- Dependências do plugin.

O engine deverá produzir um relatório por componente: aplicado, não aplicável, incompatível, ausente ou recusado. Componentes marcados como obrigatórios não podem falhar silenciosamente.

O NeuralPlugin Manager não deve depender exclusivamente do Ollama. A arquitetura deve usar adaptadores de backend, começando pelo backend já existente no AILocal Universal e permitindo integrações futuras.

## 7. Segurança

- Pacotes são dados não confiáveis até serem validados.
- Não executar código arbitrário durante importação ou ativação.
- Rejeitar caminhos absolutos, traversal (`..`), links simbólicos e colisões de nomes.
- Limitar tamanho comprimido, tamanho descompactado, número de arquivos e profundidade.
- Validar hashes antes de disponibilizar artefatos ao runtime.
- Validar assinatura quando existir uma chave confiável configurada.
- Exigir confirmação explícita para ferramentas que acessem arquivos, rede, shell ou outros recursos.
- Não permitir que plugins redefinam políticas de segurança do aplicativo.
- Manter log de instalação, ativação, falha e rollback sem registrar segredos.

## 8. Persistência e escopo

A configuração deve separar:

- Catálogo de plugins instalados.
- Estado habilitado/desabilitado.
- Associação entre plugin e modelo.
- Prioridade e preferências de composição.
- Versões e hashes dos artefatos.
- Histórico de instalação e rollback.

Remover um modelo não deve apagar automaticamente os plugins do usuário. Reinstalar o modelo pode recuperar as associações depois que a compatibilidade for revalidada.

## 9. Entregas incrementais

| Etapa | Entrega |
|---|---|
| NP-1 | Catálogo local, estado e associação de plugins baseados em regras |
| NP-2 | Importação/exportação de pacotes e validação do manifesto |
| NP-3 | Compositor determinístico de regras e resolução de conflitos |
| NP-4 | Adaptadores compatíveis com backends e artefatos PEFT |
| NP-5 | Perfis adaptativos com benchmark no hardware de destino |
| NP-6 | Transformações estruturais e restauração com validação rigorosa |

## 10. Estado de implementação

Este documento descreve uma proposta. A existência desta especificação e da aba planejada não significa que o NeuralPlugin Manager ou o NeuralInjector Engine já estejam implementados. Cada etapa deverá ser acompanhada por código, testes, documentação e critérios de aceitação.
