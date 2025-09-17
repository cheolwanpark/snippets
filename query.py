from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Sequence

from src.snippet.snippet_storage import Snippet
from src.vectordb.config import DBConfig, EmbeddingConfig
from src.vectordb.reader import SnippetVectorReader


logger = logging.getLogger("snippet_extractor")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query stored snippets from the vector database",
    )
    parser.add_argument(
        "query",
        help="Free-form text used to search the snippet collection",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of snippets to return (default: 5)",
    )
    parser.add_argument(
        "--qdrant-url",
        dest="qdrant_url",
        default=None,
        help="Override Qdrant service URL (defaults to QDRANT_URL env variable)",
    )
    parser.add_argument(
        "--qdrant-api-key",
        dest="qdrant_api_key",
        default=None,
        help="Override Qdrant API key (defaults to QDRANT_API_KEY env variable)",
    )
    parser.add_argument(
        "--qdrant-collection",
        dest="qdrant_collection",
        default="snippet_embeddings",
        help="Collection name to query (default: snippet_embeddings)",
    )
    parser.add_argument(
        "--google-api-key",
        dest="google_api_key",
        default=None,
        help=(
            "Override Google Gemini API key (defaults to GEMINI_API_KEY or GOOGLE_API_KEY env variables)"
        ),
    )
    parser.add_argument(
        "--lambda-coef",
        dest="lambda_coef",
        type=float,
        default=0.7,
        help="Diversity weight passed to the MMR search (default: 0.7)",
    )

    return parser.parse_args()


def build_reader(args: argparse.Namespace) -> SnippetVectorReader:
    db_config = DBConfig(
        url=args.qdrant_url or os.getenv("QDRANT_URL"),
        api_key=args.qdrant_api_key or os.getenv("QDRANT_API_KEY"),
        collection_name=args.qdrant_collection,
    )

    embedding_config = EmbeddingConfig(api_key=args.google_api_key)

    return SnippetVectorReader(
        db_config,
        embedding_config,
        lambda_coef=args.lambda_coef,
    )


def format_snippets(snippets: Sequence[Snippet]) -> str:
    if not snippets:
        return "List of Snippets (0)\nNo results found."

    lines: list[str] = [f"List of Snippets ({len(snippets)})"]
    for index, snippet in enumerate(snippets, start=1):
        lines.extend(
            [
                "",
                f"{index}. {snippet.title}",
                f"   Description: {snippet.description}",
                f"   Source: {snippet.filename}",
                f"   Language: {snippet.language}",
                "   Code:",
                "   ```",
            ]
        )
        code_lines = snippet.code.splitlines() or [""]
        for code_line in code_lines:
            lines.append(f"   {code_line}")
        lines.append("   ```")

    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    args = parse_args()

    if args.limit <= 0:
        print("--limit must be a positive integer", file=sys.stderr)
        sys.exit(2)

    reader = build_reader(args)

    try:
        snippets = reader.query(args.query, limit=args.limit)
    except Exception:  # pragma: no cover - defensive guard for CLI usage
        logger.exception("Vector DB query failed")
        print("❌ Query failed. See log for details.", file=sys.stderr)
        sys.exit(1)

    print(format_snippets(snippets))


if __name__ == "__main__":
    main()
