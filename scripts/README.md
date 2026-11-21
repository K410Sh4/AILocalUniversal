# Scripts

## Smoke test do RAG com Ollama real

O script `smoke_test_embeddings.py` testa a conexão com `POST /api/embed`, gera embeddings para dois textos sintéticos, grava-os em SQLite temporário e verifica se uma consulta idêntica recupera o trecho esperado.

~~~bash
ollama pull embeddinggemma
.venv/bin/python scripts/smoke_test_embeddings.py --model embeddinggemma
~~~

O nome `embeddinggemma` é um modelo de exemplo documentado pelo Ollama; pode ser substituído por outro modelo de embeddings compatível. A aplicação não baixa modelos automaticamente.

Opções:

~~~bash
.venv/bin/python scripts/smoke_test_embeddings.py --model NOME_DO_MODELO --url http://127.0.0.1:11434 --timeout 90
~~~

O teste usa apenas dados sintéticos e armazenamento temporário, removido ao terminar. Não lê documentos do usuário, não altera o índice da aplicação e não testa qualidade semântica em corpus real. Um resultado aprovado confirma conectividade, dimensionalidade e o caminho vetorial básico, não a qualidade do modelo para RAG.



## Benchmark sintético de recuperação

O script `evaluate_rag.py` cria quatro documentos sintéticos em diretório temporário, indexa-os e avalia quatro perguntas com documentos relevantes conhecidos. Mede precision@k, recall@k, MRR e cobertura em nível de documento. Pode executar somente busca lexical ou busca híbrida com um modelo Ollama.

~~~bash
.venv/bin/python scripts/evaluate_rag.py
.venv/bin/python scripts/evaluate_rag.py --model embeddinggemma:latest
.venv/bin/python scripts/evaluate_rag.py --model qwen3-embedding:0.6b
~~~

Use o mesmo `--k` e as mesmas consultas para comparar modelos. A saída inclui as fontes de recuperação realmente utilizadas, quantidade de vetores e resultados por pergunta. O corpus é sintético e temporário; o benchmark é um microteste reproduzível, não substitui avaliação em documentos reais, avaliação humana ou validação factual.
