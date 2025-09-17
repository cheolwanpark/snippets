"""RQ worker entrypoints for repository ingestion."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Sequence

import redis

from ..orchestration import ExtractionPipeline
from ..vectordb.config import DBConfig, EmbeddingConfig
from ..vectordb.writer import SnippetVectorWriter
from ..utils.github_repo import GitHubRepo
from ..snippet import Snippet
from .status import RepoStatusStore

logger = logging.getLogger("snippet_extractor")


@dataclass(slots=True)
class WorkerSettings:
    """Runtime configuration for worker execution."""

    redis_url: str
    qdrant_url: str | None
    qdrant_api_key: str | None
    qdrant_collection: str
    qdrant_batch_size: int
    embedding_model: str
    embedding_api_key: str | None
    embedding_output_dim: int | None
    embedding_batch_size: int
    pipeline_max_concurrency: int
    github_token: str | None

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        def _int_env(name: str, default: int) -> int:
            raw = os.getenv(name)
            if not raw:
                return default
            try:
                return int(raw)
            except ValueError:
                logger.warning("Invalid integer for %s: %s", name, raw)
                return default

        def _optional_int(name: str) -> int | None:
            raw = os.getenv(name)
            if not raw:
                return None
            try:
                return int(raw)
            except ValueError:
                logger.warning("Invalid integer for %s: %s", name, raw)
                return None

        return cls(
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            qdrant_collection=os.getenv("QDRANT_COLLECTION_NAME", "snippet_embeddings"),
            qdrant_batch_size=_int_env("QDRANT_UPSERT_BATCH_SIZE", 100),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-004"),
            embedding_api_key=os.getenv("GOOGLE_API_KEY"),
            embedding_output_dim=_optional_int("EMBEDDING_OUTPUT_DIM"),
            embedding_batch_size=_int_env("EMBEDDING_BATCH_SIZE", 100),
            pipeline_max_concurrency=_int_env("PIPELINE_MAX_CONCURRENCY", 5),
            github_token=os.getenv("GITHUB_TOKEN"),
        )


def process_repository(
    *,
    job_id: str,
    repo_url: str,
    repo_name: str | None = None,
    branch: str | None = None,
    include_tests: bool = False,
    extensions: Sequence[str] | None = None,
    max_file_size: int | None = None,
) -> dict[str, Any]:
    """Clone a repository, extract snippets, and persist them to Qdrant."""

    settings = WorkerSettings.from_env()
    redis_client = redis.Redis.from_url(settings.redis_url)
    status_store = RepoStatusStore(redis_client)

    derived_repo_name = repo_name or _derive_repo_name(repo_url)
    status_store.ensure_record(job_id, repo_url, repo_name=derived_repo_name)

    status_store.mark_processing(job_id, message="Cloning repository", repo_name=derived_repo_name)

    try:
        with GitHubRepo(url=repo_url, branch=branch, github_token=settings.github_token) as repo:
            repo_path = repo.path
            if repo_path is None:
                raise RuntimeError("Repository path is unavailable after clone")

            pipeline = ExtractionPipeline(
                max_concurrency=settings.pipeline_max_concurrency,
                extensions=extensions,
                max_file_size=max_file_size,
                include_tests=include_tests,
            )

            status_store.mark_processing(
                job_id,
                message="Extracting snippets from repository",
                repo_name=derived_repo_name,
            )
            snippets = pipeline.run(str(repo_path))

    except Exception as exc:  # pragma: no cover - defensive logging
        reason = _format_reason(exc)
        logger.exception("Failed to process repository %s", repo_url)
        status_store.mark_failed(
            job_id,
            reason=reason,
            message="Repository processing failed",
            repo_name=derived_repo_name,
        )
        raise

    total_files = pipeline.last_run_stats.get("total_files") if pipeline.last_run_stats else None

    enriched_snippets = _enrich_snippets(
        snippets,
        repo_url=repo_url,
        repo_name=derived_repo_name,
        ingest_id=job_id,
    )

    if not enriched_snippets:
        status_store.mark_completed(
            job_id,
            message="No snippets extracted",
            repo_name=derived_repo_name,
        )
        return {
            "job_id": job_id,
            "repo_url": repo_url,
            "repo_name": derived_repo_name,
            "snippets": 0,
            "files_processed": total_files,
        }

    writer = _build_writer(settings)

    status_store.mark_processing(
        job_id,
        message=f"Persisting {len(enriched_snippets)} snippets to Qdrant",
        repo_name=derived_repo_name,
    )

    written = writer.write(enriched_snippets)

    status_store.mark_completed(
        job_id,
        message=f"Stored {written} snippets in Qdrant",
        repo_name=derived_repo_name,
    )

    return {
        "job_id": job_id,
        "repo_url": repo_url,
        "repo_name": derived_repo_name,
        "snippets": written,
        "files_processed": total_files,
    }


def _build_writer(settings: WorkerSettings) -> SnippetVectorWriter:
    db_config = DBConfig(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection_name=settings.qdrant_collection,
        upsert_batch_size=settings.qdrant_batch_size,
    )
    embedding_config = EmbeddingConfig(
        api_key=settings.embedding_api_key,
        model=settings.embedding_model,
        output_dimensionality=settings.embedding_output_dim,
        batch_size=settings.embedding_batch_size,
    )
    return SnippetVectorWriter(db_config, embedding_config)


def _enrich_snippets(
    snippets: Sequence[Snippet],
    *,
    repo_url: str,
    repo_name: str | None,
    ingest_id: str,
) -> list[Snippet]:
    enriched: list[Snippet] = []
    for snippet in snippets:
        snippet.repo = repo_name
        snippet.repo_name = repo_name
        snippet.repo_url = repo_url
        snippet.ingest_id = ingest_id
        enriched.append(snippet)
    return enriched


def _derive_repo_name(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    cleaned = repo_url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if cleaned.startswith("git@"):
        _, _, remainder = cleaned.partition(":")
        return remainder or cleaned
    try:
        from urllib.parse import urlparse

        parsed = urlparse(cleaned)
        path = (parsed.path or "").strip("/")
        return path or cleaned
    except Exception:  # pragma: no cover - defensive
        return cleaned


def _format_reason(exc: Exception) -> str:
    reason = str(exc).strip()
    return reason or exc.__class__.__name__


__all__ = ["process_repository", "WorkerSettings"]
