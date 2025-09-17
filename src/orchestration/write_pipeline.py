from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Sequence
from urllib.parse import urlparse

from .extraction import ExtractionPipeline
from ..vectordb.config import DBConfig, EmbeddingConfig
from ..vectordb.writer import SnippetVectorWriter
from ..utils import GitHubRepo

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
    branch: Optional[str] = None
    include_patterns: Optional[Sequence[str]] = None
    last_written: int = field(init=False, default=0)
    last_errors: List[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.db_config is None:
            raise ValueError("db_config is required")
        if self.embedding_config is None:
            raise ValueError("embedding_config is required")

        if self.include_patterns is not None:
            if isinstance(self.include_patterns, str):
                self.include_patterns = (self.include_patterns,)
            else:
                self.include_patterns = tuple(self.include_patterns)

    def run(
        self,
        path_or_url: str,
        *,
        top_n: Optional[int] = None,
        branch: Optional[str] = None,
        include_patterns: Optional[Sequence[str]] = None,
    ) -> int:
        """Run the write pipeline against a local path or GitHub URL."""

        if not path_or_url:
            raise ValueError("path_or_url is required")

        self.last_written = 0
        self.last_errors = []

        effective_top_n = top_n or self.top_n
        effective_branch = branch or self.branch or "main"
        if include_patterns is not None:
            if isinstance(include_patterns, str):
                effective_include_patterns = (include_patterns,)
            else:
                effective_include_patterns = tuple(include_patterns)
        else:
            effective_include_patterns = self.include_patterns

        pipeline = ExtractionPipeline(
            max_concurrency=self.concurrency,
            extensions=self.extensions,
            max_file_size=self.max_file_size,
            include_tests=self.include_tests,
        )

        def _run_for_path(path: str) -> int:
            snippets = pipeline.run(path, top_n=effective_top_n)
            self.last_errors = list(pipeline.errors)
            if not snippets:
                logger.info("No snippets extracted from %s; skipping upload", path)
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
                logger.warning(
                    "Extraction completed with %d errors", len(pipeline.errors)
                )

            self.last_written = written
            return written

        if is_github_url(path_or_url):
            with GitHubRepo(
                path_or_url,
                branch=effective_branch,
                include_patterns=effective_include_patterns,
            ) as repo_path:
                logger.info("Cloned GitHub repo %s to %s", path_or_url, repo_path)
                return _run_for_path(str(repo_path))

        return _run_for_path(path_or_url)


def write_snippets_to_vectordb(
    path_or_url: str,
    db_config: DBConfig,
    embedding_config: EmbeddingConfig,
    *,
    top_n: int = 10,
    max_file_size: Optional[int] = None,
    include_tests: bool = False,
    extensions: Optional[Sequence[str]] = None,
    concurrency: int = 5,
    branch: Optional[str] = None,
    include_patterns: Optional[Sequence[str]] = None,
) -> None:
    pipeline = WritePipeline(
        db_config=db_config,
        embedding_config=embedding_config,
        top_n=top_n,
        max_file_size=max_file_size,
        include_tests=include_tests,
        extensions=extensions,
        concurrency=concurrency,
        branch=branch,
        include_patterns=include_patterns,
    )
    pipeline.run(path_or_url)


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
