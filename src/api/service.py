"""Service-layer helpers for repository ingestion and snippet search."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import List

from fastapi import HTTPException
from rq import Queue

from ..vectordb.reader import SnippetVectorReader
from ..vectordb.writer import SnippetVectorWriter
from ..worker.status import RepoRecord, RepoStatusStore, STATUS_DONE
from ..worker.worker import process_repository
from ..utils.file_loader import FileLoader
from .model import (
    RepoCreateRequest,
    RepoCreateResponse,
    RepoDetailResponse,
    RepoSummary,
    SnippetQueryResponse,
    SnippetResponse,
)

logger = logging.getLogger("snippet_extractor")


@dataclass(slots=True)
class ApiSettings:
    """Runtime configuration for the API server."""

    redis_url: str
    queue_name: str
    queue_default_timeout: int
    queue_result_ttl: int | None
    status_ttl: int | None
    qdrant_url: str | None
    qdrant_api_key: str | None
    qdrant_collection: str
    qdrant_facet_limit: int
    embedding_model: str
    embedding_api_key: str | None
    embedding_batch_size: int
    embedding_output_dim: int | None

    @classmethod
    def from_env(cls) -> "ApiSettings":
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
            queue_name=os.getenv("RQ_QUEUE_NAME", "repo-ingest"),
            queue_default_timeout=_int_env("RQ_DEFAULT_TIMEOUT", 30 * 60),
            queue_result_ttl=_optional_int("RQ_RESULT_TTL"),
            status_ttl=_optional_int("REPO_STATUS_TTL"),
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            qdrant_collection=os.getenv("QDRANT_COLLECTION_NAME", "snippet_embeddings"),
            qdrant_facet_limit=_int_env("QDRANT_FACET_LIMIT", 1000),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-004"),
            embedding_api_key=os.getenv("GOOGLE_API_KEY"),
            embedding_batch_size=_int_env("EMBEDDING_BATCH_SIZE", 100),
            embedding_output_dim=_optional_int("EMBEDDING_OUTPUT_DIM"),
        )


def record_to_summary(record: RepoRecord) -> RepoSummary:
    return RepoSummary(
        id=record.id,
        url=record.url,
        repo_name=record.repo_name,
        status=record.status,
        process_message=record.process_message,
        fail_reason=record.fail_reason,
        progress=record.progress,
    )


def derive_repo_name(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip()
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


def enqueue_repository_service(
    payload: RepoCreateRequest,
    queue: Queue,
    status_store: RepoStatusStore,
    settings: ApiSettings,
    *,
    vector_writer: SnippetVectorWriter,
) -> RepoCreateResponse:
    repo_name = payload.repo_name or derive_repo_name(payload.url)

    try:
        existing_record = status_store.find_by_url(payload.url)
        if existing_record is not None:
            repo_name = existing_record.repo_name or repo_name
            logger.info(
                "Replacing existing ingest %s for %s", existing_record.id, payload.url
            )
            status_store.delete(
                existing_record.id,
                queue=queue,
                vector_writer=vector_writer,
                repo_name=repo_name,
                repo_url=existing_record.url,
            )

        if payload.url:
            removed_vectors = status_store.delete(
                repo_id=None,
                vector_writer=vector_writer,
                repo_name=repo_name,
                repo_url=payload.url,
            )
            if removed_vectors:
                logger.info("Cleared stored snippets for %s", payload.url)
    except Exception as exc:
        logger.exception("Failed to purge existing repository state for %s", payload.url)
        raise HTTPException(
            status_code=500,
            detail="Failed to remove existing repository state",
        ) from exc

    repo_id = uuid.uuid4().hex

    record = status_store.create_pending(repo_id, payload.url, repo_name=repo_name)

    patterns = list(payload.patterns) if payload.patterns else list(FileLoader.DEFAULT_PATTERNS)

    job_kwargs = {
        "job_id": repo_id,
        "repo_url": payload.url,
        "repo_name": repo_name,
        "branch": payload.branch,
        "include_tests": payload.include_tests,
        "patterns": patterns,
        "max_file_size": payload.max_file_size,
    }

    try:
        queue.enqueue(process_repository, kwargs=job_kwargs, job_id=repo_id)
    except Exception as exc:  # pragma: no cover - transport error guard
        logger.exception("Failed to enqueue repository job for %s", payload.url)
        status_store.mark_failed(repo_id, reason=str(exc) or exc.__class__.__name__)
        raise HTTPException(status_code=500, detail="Failed to enqueue repository job")

    return RepoCreateResponse(**record_to_summary(record).model_dump())


def list_repositories_service(
    status_store: RepoStatusStore,
    reader: SnippetVectorReader,
    settings: ApiSettings,
) -> List[RepoSummary]:
    records = status_store.list_records()

    summaries: List[RepoSummary] = []
    summary_index: dict[str, int] = {}
    for record in records:
        summary = record_to_summary(record)
        summary_index[summary.id] = len(summaries)
        summaries.append(summary)

    try:
        completed_metadata = reader.list_completed_repositories(
            limit=settings.qdrant_facet_limit,
        )
    except Exception:
        logger.debug("Failed to load completed repositories from Qdrant", exc_info=True)
    else:
        for metadata in completed_metadata:
            completed_summary = RepoSummary(
                id=metadata.ingest_id,
                url=metadata.repo_url,
                repo_name=metadata.repo_name,
                status=STATUS_DONE,
                process_message="Completed",
                fail_reason=None,
                progress=100,
            )

            existing_index = summary_index.get(metadata.ingest_id)
            if existing_index is None:
                summary_index[metadata.ingest_id] = len(summaries)
                summaries.append(completed_summary)
            else:
                summaries[existing_index] = completed_summary

    return summaries


def get_repository_service(
    repo_id: str,
    status_store: RepoStatusStore,
    reader: SnippetVectorReader,
) -> RepoDetailResponse:
    record = status_store.get(repo_id)
    if record is None:
        try:
            completed = reader.get_completed_repository(repo_id)
        except Exception:
            logger.debug("Failed to fetch completed repository %s", repo_id, exc_info=True)
            completed = None

        if completed is None:
            raise HTTPException(status_code=404, detail="Repository not found")

        return RepoDetailResponse(
            id=completed.ingest_id,
            url=completed.repo_url,
            repo_name=completed.repo_name,
            status=STATUS_DONE,
            process_message="Completed",
            fail_reason=None,
            progress=100,
            created_at=None,
            updated_at=None,
            snippet_count=completed.snippet_count,
        )

    snippet_count: int | None = None
    if record.repo_name:
        try:
            snippet_count = reader.count_snippets_for_repo(record.repo_name)
        except Exception:
            logger.debug("Failed to fetch snippet count for %s", record.repo_name, exc_info=True)

    summary = record_to_summary(record)
    return RepoDetailResponse(
        **summary.model_dump(),
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        snippet_count=snippet_count,
    )


def delete_repository_service(
    repo_id: str,
    status_store: RepoStatusStore,
    queue: Queue,
    vector_writer: SnippetVectorWriter,
) -> None:
    try:
        status_store.delete(repo_id, queue=queue, vector_writer=vector_writer)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to delete repository %s", repo_id)
        raise HTTPException(status_code=500, detail="Failed to delete repository") from exc


def query_snippets_service(
    query: str,
    limit: int,
    reader: SnippetVectorReader,
    *,
    repo_name: str | None = None,
    language: str | None = None,
) -> SnippetQueryResponse:
    try:
        snippets = reader.query(
            query,
            limit=limit,
            repo_name=repo_name,
            language=language,
        )
    except Exception as exc:  # pragma: no cover - embed/search errors
        logger.exception("Snippet query failed")
        raise HTTPException(status_code=500, detail=f"Snippet query failed: {exc}") from exc

    results = [SnippetResponse.from_snippet(snippet) for snippet in snippets]
    return SnippetQueryResponse(query=query, results=results)


__all__ = [
    "ApiSettings",
    "record_to_summary",
    "derive_repo_name",
    "enqueue_repository_service",
    "list_repositories_service",
    "get_repository_service",
    "delete_repository_service",
    "query_snippets_service",
]
