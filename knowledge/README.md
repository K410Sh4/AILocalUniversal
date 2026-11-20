# Conhecimento e RAG

## Estado

Base inicial da Fase 3 em desenvolvimento na branch \`feature/rag-v1\`; ainda não integrada ao Chat nem à \`main\`.

## Componentes

- \`loaders.py\`: carregamento explícito de TXT e formatos técnicos UTF-8, Markdown e PDF opcional via pypdf.
- \`chunking.py\`: divisão determinística com limites, sobreposição, offsets Unicode, páginas e seções Markdown.
- \`index.py\`: persistência e recuperação lexical local por SQLite FTS5.
- \`vectors.py\`: embeddings pelo Ollama \`/api/embed\` e armazenamento vetorial SQLite com similaridade cosseno.
- \`retrieval.py\`: fusão RRF e contratos opcionais para backend vetorial e reranker.
- \`context.py\`: Context Composer com citações estáveis e limite em caracteres.
- \`validation.py\`: verificação estrutural de hash, trecho e localizador da evidência.
- \`ingestion.py\`: fluxo explícito load → chunk → index lexical.

## Limites declarados

O provedor vetorial requer um modelo de embeddings explicitamente instalado no Ollama; ele é distinto do modelo de chat. Ainda não há reranker concreto, OCR, coleta automática de arquivos ou ligação ao Cognitive Pipeline/UI. Scores ordenam resultados, mas não são probabilidades. Citações estruturalmente válidas não provam que a alegação do LLM seja verdadeira ou esteja logicamente sustentada pela fonte.

Para PDF instale o extra opcional:

~~~bash
pip install -e ".[documents]"
~~~

Consulte [docs/RAG.md](../docs/RAG.md), [contratos](../docs/DATA_CONTRACTS.md) e [segurança](../docs/SECURITY.md).
