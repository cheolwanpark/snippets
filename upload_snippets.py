from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional, Sequence

from src.orchestration.write_pipeline import write_snippets_to_vectordb
from src.vectordb.config import DBConfig, EmbeddingConfig


logger = logging.getLogger("snippet_extractor")


def _parse_extensions(raw: Optional[Sequence[str]]) -> Optional[Sequence[str]]:
    if not raw:
        return None
    return [ext if ext.startswith(".") else f".{ext}" for ext in raw]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract snippets from a directory and upload them to Qdrant"
    )
    parser.add_argument("directory", help="Directory to scan for source files")
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Maximum snippets per file (default: 10)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum concurrent extraction jobs (default: 5)",
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=None,
        help="Maximum file size to process in bytes (default: 1MB)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in processing",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        help="Override the list of file extensions to include",
    )
    parser.add_argument(
        "--qdrant-api-key",
        dest="qdrant_api_key",
        default=None,
        help="Qdrant API key (defaults to QDRANT_API_KEY env variable)",
    )
    parser.add_argument(
        "--qdrant-url",
        dest="qdrant_url",
        default=None,
        help="Qdrant service URL (defaults to QDRANT_URL env variable)",
    )
    parser.add_argument(
        "--qdrant-collection",
        dest="qdrant_collection",
        default="snippet_embeddings",
        help="Qdrant collection name (default: snippet_embeddings)",
    )
    parser.add_argument(
        "--google-api-key",
        dest="google_api_key",
        default=None,
        help="Google Gemini API key (defaults to GEMINI_API_KEY/GOOGLE_API_KEY env variables)",
    )

    args = parser.parse_args()

    directory = os.path.abspath(args.directory)
    if not os.path.exists(directory):
        parser.error(f"Directory does not exist: {directory}")

    qdrant_api_key = args.qdrant_api_key or os.getenv("QDRANT_API_KEY")
    qdrant_url = args.qdrant_url or os.getenv("QDRANT_URL")
    google_api_key = args.google_api_key or os.getenv("GOOGLE_API_KEY")

    db_config = DBConfig(
        url=qdrant_url,
        api_key=qdrant_api_key,
        collection_name=args.qdrant_collection,
    )

    embedding_config = EmbeddingConfig(api_key=google_api_key)

    extensions = _parse_extensions(args.extensions)

    try:
        write_snippets_to_vectordb(
            directory,
            db_config,
            embedding_config=embedding_config,
            top_n=args.top_n,
            max_file_size=args.max_file_size,
            include_tests=args.include_tests,
            extensions=extensions,
            concurrency=args.concurrency,
        )
    except KeyboardInterrupt:
        print("\n⚠️ Operation interrupted", file=sys.stderr)
        sys.exit(1)
    except Exception:
        logger.exception("Failed to upload snippets to vector DB")
        print("❌ Upload failed. See log for details.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
