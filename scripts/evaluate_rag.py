"""Benchmark sintético local de recuperação lexical/híbrida.

Usa somente documentos sintéticos temporários. Não lê a biblioteca pessoal do usuário.
Execute uma vez por modelo para comparar configurações com as mesmas consultas.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from knowledge.evaluation import evaluate_rankings
from knowledge.library import KnowledgeLibrary

CORPUS = [
    {
        "title": "gpu-vulkan.md",
        "content": (
            "# GPU AMD e Vulkan\n\n"
            "O backend Vulkan do Ollama pode acelerar a inferência na GPU AMD Radeon "
            "RX 5700 XT, identificada como Navi 10 e RADV. O driver do kernel Linux "
            "é amdgpu e o dispositivo gráfico é exposto pelo Vulkan."
        ),
        "query": "Qual tecnologia de renderização acelera processamento na placa AMD?",
    },
    {
        "title": "semantic-search.md",
        "content": (
            "# Recuperação semântica\n\n"
            "Modelos de embeddings transformam perguntas e trechos documentais em "
            "vetores densos. A similaridade cosseno compara a proximidade entre esses "
            "vetores e permite encontrar textos com significado relacionado mesmo "
            "quando as palavras não são idênticas."
        ),
        "query": "Como comparar o significado de uma pergunta com textos arquivados?",
    },
    {
        "title": "evidence-provenance.md",
        "content": (
            "# Proveniência de evidências\n\n"
            "Cada documento indexado mantém URI de origem e hash SHA-256. Os trechos "
            "preservam offsets, seção ou página, document_id e chunk_id. A validação "
            "confere se a citação continua apontando para o conteúdo original."
        ),
        "query": "Como auditar a origem e integridade de um conteúdo recuperado?",
    },
    {
        "title": "qt-workers.md",
        "content": (
            "# Workers de interface\n\n"
            "Operações demoradas de leitura, indexação e consultas devem rodar em "
            "QThread workers. Os sinais enviam progresso e resultados à thread gráfica, "
            "evitando congelar a janela durante o processamento."
        ),
        "query": "Como impedir que a leitura e indexação de arquivos congele a janela?",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=None,
        help="Modelo Ollama de embeddings; sem este argumento avalia busca lexical.",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="URL do Ollama (padrão: %(default)s).",
    )
    parser.add_argument(
        "--k", type=int, default=3,
        help="Corte das métricas (padrão: %(default)s).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.k < 1:
        raise SystemExit("--k precisa ser positivo.")

    with tempfile.TemporaryDirectory(prefix="ailocal-rag-eval-") as temporary:
        root = Path(temporary)
        source_directory = root / "sources"
        data_directory = root / "index"
        source_directory.mkdir()
        paths: list[Path] = []
        for item in CORPUS:
            path = source_directory / item["title"]
            path.write_text(item["content"], encoding="utf-8")
            paths.append(path)

        with KnowledgeLibrary(
            data_directory,
            ollama_url=args.ollama_url,
            embedding_model=args.model,
        ) as library:
            ingestion = library.ingest_files(paths)
            if ingestion["failed"]:
                raise RuntimeError(
                    "Falha ao ingerir corpus sintético: "
                    + json.dumps(ingestion["items"], ensure_ascii=False)
                )

            documents = library.list_documents()
            ids_by_title = {
                str(item["title"]): str(item["document_id"])
                for item in documents
            }
            missing = [
                item["title"]
                for item in CORPUS
                if item["title"] not in ids_by_title
            ]
            if missing:
                raise RuntimeError(f"Documentos ausentes no índice: {missing}")

            rankings: list[list[str]] = []
            relevant: list[set[str]] = []
            per_query: list[dict[str, Any]] = []
            retrieval_sources: set[str] = set()

            for item in CORPUS:
                bundle = library.search(item["query"], limit=args.k, max_chars=12_000)
                ranking = [
                    str(evidence.metadata["document_id"])
                    for evidence in bundle.evidence
                    if evidence.metadata.get("document_id")
                ]
                rankings.append(ranking)
                relevant_id = ids_by_title[item["title"]]
                relevant.append({relevant_id})
                for evidence in bundle.evidence:
                    retrieval_sources.update(
                        evidence.metadata.get("retrieval_sources", [])
                    )
                per_query.append(
                    {
                        "query": item["query"],
                        "expected_document": item["title"],
                        "retrieved_documents": [
                            next(
                                (
                                    title
                                    for title, document_id in ids_by_title.items()
                                    if document_id == document_id_value
                                ),
                                document_id_value,
                            )
                            for document_id_value in dict.fromkeys(ranking)
                        ],
                        "expected_document_found": relevant_id in ranking,
                    }
                )

            metrics = evaluate_rankings(rankings, relevant, k=args.k)
            vector_count = library.vector_store.count(args.model) if args.model else 0
            vector_warnings = [
                str(item["vector_warning"])
                for item in ingestion["items"]
                if item.get("vector_warning")
            ]
            result = {
                "status": "partial" if vector_warnings else "completed",
                "mode": "hybrid" if vector_count else "lexical",
                "embedding_model": args.model,
                "vectors_for_model": vector_count,
                "vector_warnings": vector_warnings,
                "retrieval_sources": sorted(retrieval_sources),
                "metrics": metrics,
                "cases": per_query,
                "storage": "temporary_and_removed",
                "documents": len(CORPUS),
                "corpus": "synthetic_only",
                "scope": (
                    "Microbenchmark reproduzível; não representa qualidade em corpus "
                    "real nem comprova veracidade factual."
                ),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
