"""Utilities for working with remote GitHub repositories."""

from __future__ import annotations

import fnmatch
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Sequence


logger = logging.getLogger("snippet_extractor")


class GitHubRepo:
    """Clone GitHub repositories into a temporary directory.

    Designed for use as a context manager::

        with GitHubRepo(url) as repo_path:
            ...

    The underlying temporary directory is automatically removed when the
    context exits.
    """

    def __init__(
        self,
        url: str,
        branch: str | None = None,
        include_patterns: Sequence[str] | None = None,
    ) -> None:
        self.url = url
        self.branch = branch or "main"
        if isinstance(include_patterns, str):
            self.include_patterns: tuple[str, ...] = (include_patterns,)
        elif include_patterns is not None:
            self.include_patterns = tuple(include_patterns)
        else:
            self.include_patterns = ()

        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._repo_path: Path | None = None

    def __enter__(self) -> Path:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="snippets_repo_")
        base_dir = Path(self._temp_dir.name)
        repo_dir = base_dir / "repo"

        try:
            self._clone_repository(repo_dir)
            if self.include_patterns:
                self._apply_include_patterns(repo_dir, self.include_patterns)
        except Exception:
            self.cleanup()
            raise

        self._repo_path = repo_dir
        return repo_dir

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        """Remove the temporary directory if it exists."""

        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None
        self._repo_path = None

    @property
    def path(self) -> Path | None:
        """Return the current repository path, if available."""

        return self._repo_path

    def _clone_repository(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            self.branch,
            "--single-branch",
            self.url,
            str(destination),
        ]

        logger.debug(
            "Cloning repository %s (branch=%s) into %s", self.url, self.branch, destination
        )

        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            stdout = result.stdout.decode("utf-8", errors="ignore")
            stderr = result.stderr.decode("utf-8", errors="ignore")
            logger.error(
                "Failed to clone repository %s (branch=%s): %s",
                self.url,
                self.branch,
                stderr.strip() or stdout.strip(),
            )
            raise RuntimeError(
                f"Failed to clone repository {self.url} (branch {self.branch}): {stderr.strip() or stdout.strip()}"
            )

    def _apply_include_patterns(
        self, repo_dir: Path, patterns: Iterable[str]
    ) -> None:
        patterns = tuple(p.strip() for p in patterns if p.strip())
        if not patterns:
            return

        logger.debug(
            "Filtering repository %s with include patterns: %s",
            repo_dir,
            ", ".join(patterns),
        )

        matched_paths: set[Path] = set()
        for file_path in repo_dir.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(repo_dir)
            rel_str = rel_path.as_posix()

            if self._matches_patterns(rel_str, patterns):
                matched_paths.add(file_path)
            else:
                file_path.unlink(missing_ok=True)

        if not matched_paths:
            logger.warning(
                "No files matched include patterns %s in repository %s",
                patterns,
                repo_dir,
            )

        self._remove_empty_directories(repo_dir)

    @staticmethod
    def _matches_patterns(path_str: str, patterns: Iterable[str]) -> bool:
        for pattern in patterns:
            normalized = pattern.rstrip("/")
            if not normalized:
                continue

            if fnmatch.fnmatch(path_str, normalized):
                return True

            if path_str.startswith(normalized + "/"):
                return True

        return False

    @staticmethod
    def _remove_empty_directories(root: Path) -> None:
        for directory in sorted(
            (d for d in root.rglob("*") if d.is_dir()),
            key=lambda d: len(d.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                shutil.rmtree(directory, ignore_errors=True)
