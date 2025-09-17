from __future__ import annotations

import logging
import subprocess
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
    ) -> int:
        """Run the write pipeline against a prepared GitHub repository checkout."""

        if not repo_path:
            raise ValueError("repo_path is required")

        repo_path = Path(repo_path)
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        self.last_written = 0
        self.last_errors = []

        pipeline = ExtractionPipeline(
            max_concurrency=self.concurrency,
            extensions=self.extensions,
            max_file_size=self.max_file_size,
            include_tests=self.include_tests,
        )

        logger.info("Processing repository at %s", repo_path)
        snippets = pipeline.run(str(repo_path))
        self.last_errors = list(pipeline.errors)
        if not snippets:
            logger.info("No snippets extracted from %s; skipping upload", repo_path)
            self.last_written = 0
            return 0

        repo_identifier = self._resolve_repo_identifier(repo_path)
        if repo_identifier:
            for snippet in snippets:
                snippet.repo = repo_identifier
        else:
            logger.debug("Unable to resolve repository identifier for %s", repo_path)

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

    def _resolve_repo_identifier(self, repo_path: Path) -> str | None:
        base_path = repo_path if repo_path.is_dir() else repo_path.parent
        repo_root = self._git_toplevel(base_path) or base_path

        owner_repo = self._parse_remote(
            self._run_git_command(repo_root, ["remote", "get-url", "origin"])
        )
        branch = self._run_git_command(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]) or "HEAD"

        owner_repo = owner_repo or f"local/{repo_root.name}"
        branch = branch.strip() or "HEAD"
        return f"{owner_repo}/{branch}"

    @staticmethod
    def _parse_remote(remote: str | None) -> str | None:
        if not remote:
            return None

        remote = remote.strip()
        if not remote:
            return None

        if remote.startswith("git@"):
            try:
                _, path_part = remote.split(":", 1)
            except ValueError:
                return None
            path = path_part
        else:
            parsed = urlparse(remote)
            path = parsed.path

        path = (path or "").lstrip("/")
        if path.endswith(".git"):
            path = path[:-4]

        if not path:
            return None

        segments = [segment for segment in path.split("/") if segment]
        if len(segments) < 2:
            return None

        owner, name = segments[0], segments[1]
        return f"{owner}/{name}"

    @staticmethod
    def _git_toplevel(candidate_path: Path) -> Path | None:
        output = WritePipeline._run_git_command(candidate_path, ["rev-parse", "--show-toplevel"])
        if not output:
            return None
        return Path(output)

    @staticmethod
    def _run_git_command(path: Path, args: list[str]) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(path), *args],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, ValueError):  # pragma: no cover - git not available
            return None

        if result.returncode != 0:
            return None

        return result.stdout.strip()


def write_snippets_to_vectordb(
    repo_path: Union[str, Path],
    db_config: DBConfig,
    embedding_config: EmbeddingConfig,
    *,
    max_file_size: Optional[int] = None,
    include_tests: bool = False,
    extensions: Optional[Sequence[str]] = None,
    concurrency: int = 5,
) -> None:
    pipeline = WritePipeline(
        db_config=db_config,
        embedding_config=embedding_config,
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
