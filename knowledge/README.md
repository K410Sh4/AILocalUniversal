# Conhecimento e RAG

## Estado

Base da Fase 3 em desenvolvimento na branch `feature/rag-v1`. O serviço e a aba de gestão documental foram implementados; a integração automática ao Chat permanece pendente.

## Componentes

- `loaders.py`: carregamento explícito de TXT e formatos técnicos UTF-8, Markdown e PDF opcional via pypdf.
- `chunking.py`: divisão determinística com limites, sobreposição, offsets Unicode, páginas e seções Markdown.
- `index.py`: persistência e recuperação lexical local por SQLite FTS5.
- `vectors.py`: embeddings pelo Ollama `/api/embed` e armazenamento vetorial SQLite com similaridade cosseno.
- `retrieval.py`: fusão RRF e contratos opcionais para backend vetorial e reranker.
- `context.py`: Context Composer com citações estáveis e limite em caracteres.
- `validation.py`: verificação estrutural de hash, trecho e localizador da evidência.
- `ingestion.py`: fluxo explícito load → chunk → index lexical.
- `library.py`: biblioteca persistente para ingestão, listagem, busca, remoção do índice e reindexação por modelo de embeddings.
- `runtime.py`: ponte independente para anexar evidências a CognitiveTask e compor mensagem documental não confiável.
- `app/views/knowledge_view.py`: aba PySide6 para seleção de arquivos, listagem, remoção e prévia de busca.
- `workers/knowledge_workers.py`: operações documentais em QThread.

## Persistência e comportamento

A biblioteca fica em `$XDG_DATA_HOME/ailocal-universal/knowledge`, com fallback em `~/.local/share/ailocal-universal/knowledge`. Diretórios usam modo 0700 e bancos SQLite modo 0600 no Linux.

A remoção apaga somente dados do índice; o arquivo original não é modificado. O modelo de embeddings é separado do modelo de chat e a sua troca exige reindexação explícita. A aba Conhecimento não injeta documentos automaticamente no Chat.

## Limites declarados

Ainda não há reranker concreto, OCR, citações apresentadas no balão do Chat, benchmark de recuperação em corpus representativo nem integração automática do KnowledgeRuntime ao MainWindow/CognitiveTaskExecutor. A validação de integridade das citações não prova a verdade das alegações do LLM.

Para PDF instale o extra opcional:

~~~bash
pip install -e ".[documents]"
~~~

Consulte [docs/RAG.md](../docs/RAG.md), [contratos](../docs/DATA_CONTRACTS.md) e [segurança](../docs/SECURITY.md).
