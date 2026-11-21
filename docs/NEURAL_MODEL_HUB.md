# NeuralModel Hub

## Objetivo

O NeuralModel Hub é a camada de catálogo, descoberta e avaliação de modelos do AILocal Universal. Ele separa quatro conceitos:

1. **Ficha do modelo:** família, categoria, capacidades, modalidades, arquitetura, parâmetros, contexto, publicador, licença e procedência.
2. **Variante/artefato:** referência exata do runtime, quantização, tamanho publicado, digest e estado instalado.
3. **Perfil de hardware:** CPU, RAM, disco e aceleradores detectáveis.
4. **Compatibilidade:** avaliação dos requisitos de execução verificados contra recursos medidos.

## Fases 4.1 e 4.2 — registro local e hardware

- Contratos versionáveis para fichas, artefatos e requisitos.
- Registro JSON local em diretório XDG, escrita atômica e permissões restritas no Linux.
- Descoberta dos modelos instalados no Ollama e sincronização sem apagar metadados curados.
- Perfil de CPU, RAM disponível, armazenamento livre e GPUs expostas pelo sysfs DRM do Linux.
- Avaliação em três estados: **compatível**, **incompatível** e **não avaliado**.

## Fase 4.3 — catálogo remoto por categorias

- O catálogo é um manifesto JSON versionado, servido pela branch do projeto e empacotado como fallback.
- Cada ficha contém fontes oficiais do Ollama, desenvolvedor, categorias, capacidades, modalidades, licença quando verificada e variantes/tag.
- Categorias suportadas: LLMs/conversação, programação, raciocínio, visão, áudio/voz, multimodais, embeddings/RAG, rerankers, geração de imagem/vídeo/música, OCR, detecção de objetos, tradução e agentes.
- Pesquisa textual e filtro de categoria mostram apenas modelos incluídos no catálogo curado.
- Cada variante tem uma referência exata e plataformas permitidas. Uma variante sem suporte no sistema atual não habilita a ação de instalação.
- Atualização remota tem limite de 2 MiB, validação de esquema e validação das URLs/referências; falha remota usa o manifesto local e exibe aviso.
- Categorias sem uma oferta Ollama curada permanecem vazias; o Hub não inventa suporte ou artefatos.

## Fase 4.4 — instalação e gerenciamento pelo Ollama

- O usuário seleciona uma variante e confirma o nome exato, o tamanho publicado e a situação da licença antes do download.
- A instalação usa `POST /api/pull` do Ollama e processa o stream NDJSON em worker Qt separado da interface.
- Progresso por camada, estados do runtime, erros e cancelamento cooperativo são exibidos na interface.
- O término só é considerado sucesso após o evento final `success` do Ollama.
- Cancelar encerra o stream local; o Ollama pode retomar camadas já baixadas numa tentativa posterior.
- Remoção usa `DELETE /api/delete` e sempre pede confirmação explícita.
- Após instalação/remoção, o inventário real do Ollama é consultado novamente para atualizar o estado instalado.
- O catálogo exibe o tamanho publicado como informação de download; não o converte em requisito de RAM/VRAM nem afirma espaço livre no volume usado pelo Ollama.

## Regras de factualidade e segurança

O inventário local do Ollama confirma somente os modelos que o runtime reporta, tamanho em disco e digest quando disponível. Isso não prova licença, publicador, arquitetura, parâmetros, quantização, janela de contexto ou requisitos de execução.

A lista inicial é curada e versionada pelo projeto, não uma varredura livre da internet. Referências instaláveis são validadas e só são aceitas como nomes de modelo Ollama, nunca URLs ou comandos arbitrários. O download é delegado ao runtime, evitando executar scripts ou instalar pacotes de fontes não verificadas.

Metadados ausentes permanecem não informados. Licenças não verificadas são destacadas antes da instalação. Tamanho publicado não é estimativa de VRAM: pesos carregados, cache KV, comprimento do contexto, buffers, offload, backend e concorrência alteram o consumo real.

Fabricante e driver da GPU não comprovam suporte a CUDA, ROCm ou Vulkan. A compatibilidade só é declarada quando requisitos mínimos estiverem verificados e ligados a evidência.

## Próximas entregas

- Catálogo mais amplo e atualizado automaticamente, com ingestão e revisão de metadados por campo.
- Licença e proveniência por versão, quantização e artefato.
- Requisitos de memória diferenciados por runtime, quantização, contexto e offload, baseados em documentação verificável ou medições.
- Benchmarks locais de qualidade, latência, RAM, VRAM, estabilidade e estado quente/frio.
- Adaptive Model Selector, fallback explicável e integração com o Resource Manager.
- Outros runtimes e gerenciamento em plataformas adicionais.
