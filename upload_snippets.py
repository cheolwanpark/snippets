from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional, Sequence

from src.orchestration.write_pipeline import (
    is_github_url,
    write_snippets_to_vectordb,
)
from src.utils import GitHubRepo
from src.vectordb.config import DBConfig, EmbeddingConfig


logger = logging.getLogger("snippet_extractor")


def _parse_extensions(raw: Optional[Sequence[str]]) -> Optional[Sequence[str]]:
    if not raw:
        return None
    return [ext if ext.startswith(".") else f".{ext}" for ext in raw]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract snippets from a GitHub repository and upload them to Qdrant"
    )
    parser.add_argument(
        "repo_url",
        help="GitHub repository URL (https://, ssh, git@)",
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
    parser.add_argument(
        "--branch",
        default=None,
        help="Branch to clone when fetching the GitHub repository",
    )
    parser.add_argument(
        "--include-pattern",
        dest="include_patterns",
        action="append",
        help="Glob pattern to keep when cloning from GitHub (can be repeated)",
    )
    parser.add_argument(
        "--github-token",
        dest="github_token",
        default=None,
        help="Personal access token for private GitHub repositories (defaults to GITHUB_TOKEN env variable)",
    )

    args = parser.parse_args()

    repo_url = args.repo_url
    if not is_github_url(repo_url):
        parser.error("Only GitHub repository URLs are supported.")

    qdrant_api_key = args.qdrant_api_key or os.getenv("QDRANT_API_KEY")
    qdrant_url = args.qdrant_url or os.getenv("QDRANT_URL")
    google_api_key = args.google_api_key or os.getenv("GOOGLE_API_KEY")
    github_token = args.github_token or os.getenv("GITHUB_TOKEN")

    db_config = DBConfig(
        url=qdrant_url,
        api_key=qdrant_api_key,
        collection_name=args.qdrant_collection,
    )

    embedding_config = EmbeddingConfig(api_key=google_api_key)

    extensions = _parse_extensions(args.extensions)

    try:
        with GitHubRepo(
            repo_url,
            branch=args.branch,
            include_patterns=args.include_patterns,
            github_token=github_token,
        ) as github_repo:
            repo_path = github_repo.path
            if repo_path is None:
                raise RuntimeError("Failed to resolve local path for cloned repository")

            write_snippets_to_vectordb(
                repo_path,
                db_config,
                embedding_config=embedding_config,
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
