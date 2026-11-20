# NeuralModel Hub

## Objetivo

O NeuralModel Hub é a camada de catálogo, descoberta e avaliação de modelos do AILocal Universal. Ele separa quatro conceitos que não devem ser confundidos:

1. **Ficha do modelo:** família, categoria, capacidades, modalidades, arquitetura, parâmetros, contexto, publicador, licença e procedência.
2. **Artefato/runtime:** referência instalada, runtime, digest, quantização e tamanho do artefato em disco.
3. **Perfil de hardware:** CPU, RAM, disco e aceleradores detectáveis.
4. **Compatibilidade:** avaliação dos requisitos de execução verificados contra recursos efetivamente medidos.

O catálogo não é uma lista fixa de nomes. O inventário local do Ollama cria fichas iniciais, que podem ser complementadas por fontes curadas sem perder os metadados descobertos pelo runtime.

## Entrega inicial — fases 4.1 e 4.2 (em validação)

- Contratos versionáveis para fichas, artefatos e requisitos.
- Registro JSON local em diretório XDG, escrita atômica e permissões restritas no Linux.
- Descoberta de modelos instalados no Ollama usando o Engine Adapter já existente.
- Sincronização de inventário que marca artefatos ausentes como não instalados e preserva dados curados.
- Perfil de CPU, RAM disponível, armazenamento livre e GPUs Linux expostas pelo sysfs DRM.
- Exibição de inventário e procedência em uma nova aba NeuralModel Hub.
- Avaliação com três estados: **compatível**, **incompatível** e **não avaliado**.
- Nenhum download, instalação, execução de modelo ou acesso remoto é iniciado pelo Hub.

## Regras de factualidade e segurança

O endpoint de inventário do Ollama confirma apenas os modelos conhecidos pelo runtime, seus tamanhos em disco e digest quando informado. Isso não prova licença, publicador, arquitetura, parâmetros, quantização, janela de contexto ou requisitos de execução.

O tamanho do arquivo não é utilizado como estimativa de VRAM/RAM de inferência. Pesos carregados, cache KV, comprimento de contexto, buffers, offload, backend e concorrência mudam o consumo real.

A compatibilidade só é declarada quando os requisitos mínimos estão marcados como verificados e possuem URL de evidência. Sem essa evidência, o resultado é **não avaliado**; o sistema não preenche lacunas com estimativas silenciosas.

A detecção do fabricante e do driver da GPU não prova suporte a CUDA, ROCm, Vulkan ou outro backend. O perfil inicial lê dados observáveis pelo Linux DRM; a disponibilidade de cada runtime será validada por adaptadores próprios.

O arquivo de catálogo é local. Se estiver corrompido ou usar esquema desconhecido, é preservado e a sessão mostra aviso em vez de sobrescrevê-lo automaticamente.

## Próximas entregas

- Adaptadores de fontes externas de catálogo com atualização, data e procedência por campo.
- Verificação de licença por família, versão, quantização e artefato distribuído.
- Probes adicionais de hardware e runtimes em outras plataformas.
- Requisitos de memória diferenciados por runtime, quantização, contexto e offload, apoiados por medições ou documentação verificável.
- Benchmarks locais de qualidade, latência, RAM, VRAM, estabilidade e estado quente/frio.
- Adaptive Model Selector baseado em tarefa, capacidades verificadas, hardware, qualidade medida e preferência do usuário.
- Instalação e remoção somente com consentimento explícito, licença apresentada, espaço livre e verificação de integridade.
