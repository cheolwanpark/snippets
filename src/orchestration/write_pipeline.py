from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Union
from urllib.parse import urlparse

from .extraction import ExtractionPipeline
from ..vectordb.config import DBConfig, EmbeddingConfig
from ..vectordb.writer import SnippetVectorWriter

logger = logging.getLogger("snippet_extractor")


@dataclass
class WritePipeline:
    """Coordinate snippet extraction and upload to the vector database."""

    db_config: DBConfig
    embedding_config: EmbeddingConfig
    top_n: int = 10
    max_file_size: Optional[int] = None
    include_tests: bool = False
    extensions: Optional[Sequence[str]] = None
    concurrency: int = 5
    last_written: int = field(init=False, default=0)
    last_errors: List[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.db_config is None:
            raise ValueError("db_config is required")
        if self.embedding_config is None:
            raise ValueError("embedding_config is required")

    def run(
        self,
        repo_path: Union[str, Path],
        *,
        top_n: Optional[int] = None,
    ) -> int:
        """Run the write pipeline against a prepared GitHub repository checkout."""

        if not repo_path:
            raise ValueError("repo_path is required")

        repo_path = Path(repo_path)
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        self.last_written = 0
        self.last_errors = []

        effective_top_n = top_n or self.top_n

        pipeline = ExtractionPipeline(
            max_concurrency=self.concurrency,
            extensions=self.extensions,
            max_file_size=self.max_file_size,
            include_tests=self.include_tests,
        )

        logger.info("Processing repository at %s", repo_path)
        snippets = pipeline.run(str(repo_path), top_n=effective_top_n)
        self.last_errors = list(pipeline.errors)
        if not snippets:
            logger.info("No snippets extracted from %s; skipping upload", repo_path)
            self.last_written = 0
            return 0

        writer = SnippetVectorWriter(self.db_config, self.embedding_config)

        written = writer.write(snippets)
        logger.info(
            "Uploaded %d snippets to Qdrant collection %s",
            written,
            self.db_config.collection_name,
        )

        if pipeline.errors:
            logger.warning("Extraction completed with %d errors", len(pipeline.errors))

        self.last_written = written
        return written


def write_snippets_to_vectordb(
    repo_path: Union[str, Path],
    db_config: DBConfig,
    embedding_config: EmbeddingConfig,
    *,
    top_n: int = 10,
    max_file_size: Optional[int] = None,
    include_tests: bool = False,
    extensions: Optional[Sequence[str]] = None,
    concurrency: int = 5,
) -> None:
    pipeline = WritePipeline(
        db_config=db_config,
        embedding_config=embedding_config,
        top_n=top_n,
        max_file_size=max_file_size,
        include_tests=include_tests,
        extensions=extensions,
        concurrency=concurrency,
    )
    pipeline.run(repo_path)


def is_github_url(value: str) -> bool:
    """Return True if the provided value appears to be a GitHub repository URL."""
    if value.startswith("git@github.com:"):
        return True

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "ssh", "git"}:
        hostname = (parsed.hostname or "").lower()
        return hostname == "github.com" or hostname.endswith(".github.com")
    return False


__all__ = ["WritePipeline", "write_snippets_to_vectordb", "is_github_url"]
