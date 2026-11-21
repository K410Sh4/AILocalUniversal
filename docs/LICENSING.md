# Licenciamento e propriedade intelectual

**Projeto:** AILocal Universal  
**Identificador SPDX:** `LicenseRef-AILocal-Universal-Proprietary`  
**Aviso público de titularidade:** Copyright © 2026 K410Sh4. Todos os direitos reservados.  
**Política:** proprietária / todos os direitos reservados.

## 1. Regra de licenciamento do projeto

O código e os materiais originais do projeto são proprietários. O arquivo raiz `LICENSE` contém os termos da licença. O identificador SPDX personalizado é usado para identificar essa licença em metadados e ferramentas; ele não transforma o projeto em software open source.

A política cobre o material original presente no repositório, inclusive material desenvolvido em branches de trabalho:
- aplicação desktop AILocal Universal;
- Cognitive Pipeline e suas etapas originais;
- CognitiveTask, Capability Vectorizer, Task Decomposer, Cognitive Planner e Orchestrator;
- Deterministic Tools, Cognitive Task Executor e Validation Layer;
- Cognitive Inspector e a interface original;
- NeuralMap: modelo de grafo, canvas/editor, runtime, handlers, validação, schemas e I/O de pacotes;
- NeuralPlugin e arquitetura do NeuralPlugin Manager;
- NeuralInjector Engine, NeuralInjector Package Specification (NIP), documentação do formato `.neuralinjector`, manifestos e schemas;
- adaptadores, perfis e políticas originais do Resource Manager, quando efetivamente implementados;
- Neural Elastic Execution: contratos de traces, simulador de cache, políticas de substituição, métricas, predição e otimização originais quando efetivamente implementados;
- componentes, protocolos, documentação e código originais de Swarm/execução cooperativa, quando efetivamente implementados;
- Brain Artificial (BA): arquitetura e expressões originais de organização, desenvolvimento, especialização, adaptação e evolução estrutural, distinta de IA convencional, somente quando efetivamente documentadas ou implementadas;
- NeuralDNA: genoma artificial, expressão epigenética, desenvolvimento da BA, avaliação ambiental, benchmarks antecipatórios, regionais e de comunicação espacial, campos de sinal morfogenético artificiais, modelos originais de transporte/remoção e documentação experimental, somente quando efetivamente presentes e pertencentes ao titular;
- documentação técnica, diagramas, templates, testes, exemplos e arquivos de configuração originais.

A Brain Artificial (BA) é uma linha de desenvolvimento distinta de modelos convencionais de Inteligência Artificial; K.IA é o runtime de coordenação separado. Essa distinção conceitual não afirma que a BA esteja completa ou operacional. O registro de componentes não significa que tudo esteja implementado. A licença protege expressões concretas que existam no repositório, não funcionalidades descritas apenas como plano. Conceitos de biologia, publicações científicas, protocolos de terceiros e tecnologias de interface neural de terceiros não são apropriados nem relicenciados pelo projeto.

## 2. O que não é coberto pela licença proprietária

Não são convertidos em propriedade do projeto pelo simples uso ou integração:
- bibliotecas, frameworks, linguagens, runtimes, ferramentas e serviços de terceiros;
- Ollama e seus componentes;
- modelos, pesos, tokenizers, adaptadores, datasets e saídas de terceiros;
- fontes, ícones, imagens, marcas ou outros ativos criados por terceiros;
- documentos, conversas, prompts, arquivos e workflows fornecidos por usuários;
- conteúdo de plugins e pacotes criados por terceiros.

Cada material excluído segue a licença ou os termos de seu próprio titular. Consulte `THIRD_PARTY_NOTICES.md`.

## 3. NeuralMap, NeuralPlugin e NeuralInjector

### NeuralMap
A implementação original do editor, grafo, runtime, handlers, integrações, schemas e documentação pertence ao escopo proprietário na medida em que seja original e esteja presente no repositório. Um workflow criado por um usuário não se torna propriedade do projeto apenas por ser editado ou executado pelo NeuralMap.

### NeuralPlugin
O código e a documentação originais do gerenciador e dos contratos pertencem ao escopo proprietário. Um plugin produzido por terceiro não passa automaticamente a pertencer ao projeto: o autor do plugin deve declarar a licença e a proveniência de seus próprios componentes.

### NeuralInjector / NIP
A implementação original do leitor, escritor, validador e gestão de pacotes, bem como a expressão documental e schemas da especificação NIP, pertencem ao escopo proprietário quando presentes no repositório. A especificação do contêiner não transfere a titularidade de pesos, adaptadores, regras, dados ou outros componentes transportados dentro de um pacote.

Todo pacote e plugin deve ter uma licença explícita para seu conteúdo. A licença do software que lê o pacote e a licença do conteúdo dentro do pacote são coisas distintas.

## 4. Marcação técnica

O valor de licença para os materiais originais é:

```text
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
```

A metadata Python declara esse identificador em `pyproject.toml` e inclui o arquivo `LICENSE`. O texto completo e a exceção de terceiros estão documentados nos arquivos `LICENSE`, `NOTICE.md` e `THIRD_PARTY_NOTICES.md`.

## 5. Dependências e distribuição comercial

O fato de o código do AILocal ser proprietário não libera o titular de cumprir as licenças de suas dependências. Em especial, PySide6/Qt for Python tem opções LGPL/GPL e comerciais. A distribuição de binários proprietários precisa ser analisada de acordo com os módulos efetivamente usados e as obrigações da modalidade escolhida. A LGPL pode permitir manter o código da aplicação fechado se suas condições forem cumpridas, mas isso não é uma autorização para ignorar as obrigações de Qt.

As dependências listadas em `pyproject.toml` são faixas de versão. Ainda não existe um SBOM completo, lockfile ou verificação automatizada de licenças de todas as dependências transitivas. Antes de distribuir instaladores, gerar um SBOM e revisar as licenças exatas.

## 6. Contribuições

Não incorporar contribuições externas ao código proprietário sem acordo escrito separado, aprovado pelo titular, que conceda os direitos necessários ao projeto. Uma issue, fork, pull request ou patch enviado não transfere automaticamente titularidade nem concede licença ao projeto. Ver também `CONTRIBUTING.md`.

## 7. Identificação do titular

`K410Sh4` é o identificador público da conta GitHub que administra o repositório e é usado como identificação pública do titular neste aviso. Para contratos, cessões, licenças comerciais, notificações formais ou requerimentos de registro, deve ser usada a identificação civil ou empresarial completa do titular correto. A troca do identificador público por nome civil ou razão social deve ser feita antes desses atos formais, com revisão jurídica.

## 8. O que esta licença não faz

A licença de software não registra automaticamente marcas, não concede patente e não transforma uma ideia abstrata, método, função técnica ou algoritmo em direito exclusivo. Em geral, o direito autoral de software protege a expressão concreta do programa; conceitos ainda não materializados não são o mesmo que código protegido. Nomes de produtos devem ser avaliados separadamente para registro de marca no INPI, e eventual patente depende de análise própria dos requisitos legais.

## 9. Registro de programa de computador no Brasil

A proteção autoral de software não depende de registro, mas o INPI oferece o Registro de Programa de Computador (RPC), baseado em documentação técnica e resumo hash. O registro pode reforçar a prova de autoria/titularidade e integridade. Ele ainda não foi solicitado por esta implementação.

Referências oficiais:
- [Lei nº 9.609/1998 — Programa de Computador](https://www.planalto.gov.br/ccivil_03/leis/l9609.htm)
- [Lei nº 9.610/1998 — Direitos Autorais](https://www.planalto.gov.br/ccivil_03/leis/l9610.htm)
- [INPI — Legislação de programas de computador](https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/legislacao-programa-de-computador)
- [INPI — Guia básico do registro de programa de computador](https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/guia-basico)
- [INPI — Serviço para solicitar registro de programa de computador](https://www.gov.br/pt-br/servicos/solicitar-o-registro-de-programa-de-computador)

Este documento é um aviso e uma política inicial de licenciamento do repositório, não substitui análise de advogado especializado em propriedade intelectual.
