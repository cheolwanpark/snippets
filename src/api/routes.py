"""FastAPI routes for repository ingestion and snippet search."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import List, Sequence

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from rq import Queue

from ..snippet import Snippet
from ..vectordb.config import DBConfig, EmbeddingConfig
from ..vectordb.reader import SnippetVectorReader
from ..worker.queue import QueueConfig, create_queue
from ..worker.status import RepoRecord, RepoStatusStore, STATUS_DONE
from ..worker.worker import process_repository

logger = logging.getLogger("snippet_extractor")

router = APIRouter()


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


class RepoCreateRequest(BaseModel):
    url: str = Field(..., description="GitHub repository URL")
    branch: str | None = Field(None, description="Repository branch or ref to clone")
    include_tests: bool = Field(False, description="Include test directories when extracting")
    extensions: Sequence[str] | None = Field(
        None, description="Optional list of file extensions to include"
    )
    max_file_size: int | None = Field(
        None,
        description="Maximum file size (bytes) to consider",
        ge=0,
    )
    repo_name: str | None = Field(
        None,
        description="Optional repository identifier to store alongside snippets",
    )


class RepoSummary(BaseModel):
    id: str
    url: str
    repo_name: str | None = None
    status: str
    process_message: str | None = None
    fail_reason: str | None = None
    progress: int | None = None


class RepoDetailResponse(RepoSummary):
    created_at: str | None = None
    updated_at: str | None = None
    snippet_count: int | None = None


class RepoCreateResponse(RepoSummary):
    pass


class SnippetResponse(BaseModel):
    title: str
    description: str
    language: str
    code: str
    path: str
    repo_name: str | None = None
    repo_url: str | None = None

    @classmethod
    def from_snippet(cls, snippet: Snippet) -> "SnippetResponse":
        return cls(
            title=snippet.title,
            description=snippet.description,
            language=snippet.language,
            code=snippet.code,
            path=snippet.path,
            repo_name=getattr(snippet, "repo_name", None) or snippet.repo,
            repo_url=getattr(snippet, "repo_url", None),
        )


class SnippetQueryResponse(BaseModel):
    query: str
    results: List[SnippetResponse]


# Dependencies -----------------------------------------------------------------


def get_settings(request: Request) -> ApiSettings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, ApiSettings):
        raise RuntimeError("API settings have not been initialised")
    return settings


def _get_redis_client(request: Request, settings: ApiSettings) -> redis.Redis:
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client is None:
        redis_client = redis.Redis.from_url(settings.redis_url)
        request.app.state.redis_client = redis_client
    return redis_client


def get_status_store(
    request: Request,
    settings: ApiSettings = Depends(get_settings),
) -> RepoStatusStore:
    redis_client = _get_redis_client(request, settings)
    return RepoStatusStore(redis_client, ttl_seconds=settings.status_ttl)


def get_queue(
    request: Request,
    settings: ApiSettings = Depends(get_settings),
) -> Queue:
    queue = getattr(request.app.state, "queue", None)
    if queue is None:
        redis_client = _get_redis_client(request, settings)
        queue_config = QueueConfig(
            redis_url=settings.redis_url,
            queue_name=settings.queue_name,
            default_timeout=settings.queue_default_timeout,
            result_ttl=settings.queue_result_ttl,
        )
        queue = create_queue(queue_config, connection=redis_client)
        request.app.state.queue = queue
    return queue


def get_vector_reader(
    request: Request,
    settings: ApiSettings = Depends(get_settings),
) -> SnippetVectorReader:
    reader = getattr(request.app.state, "vector_reader", None)
    if reader is None:
        db_config = DBConfig(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection_name=settings.qdrant_collection,
        )
        embedding_config = EmbeddingConfig(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            output_dimensionality=settings.embedding_output_dim,
            batch_size=settings.embedding_batch_size,
        )
        reader = SnippetVectorReader(db_config, embedding_config)
        request.app.state.vector_reader = reader
    return reader


# Routes ----------------------------------------------------------------------


@router.post("/repo", response_model=RepoCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_repository(
    payload: RepoCreateRequest,
    queue: Queue = Depends(get_queue),
    status_store: RepoStatusStore = Depends(get_status_store),
) -> RepoCreateResponse:
    repo_id = uuid.uuid4().hex
    repo_name = payload.repo_name or _derive_repo_name(payload.url)

    record = status_store.create_pending(repo_id, payload.url, repo_name=repo_name)

    job_kwargs = {
        "job_id": repo_id,
        "repo_url": payload.url,
        "repo_name": repo_name,
        "branch": payload.branch,
        "include_tests": payload.include_tests,
        "extensions": list(payload.extensions) if payload.extensions else None,
        "max_file_size": payload.max_file_size,
    }

    try:
        queue.enqueue(process_repository, kwargs=job_kwargs, job_id=repo_id)
    except Exception as exc:  # pragma: no cover - transport error guard
        logger.exception("Failed to enqueue repository job for %s", payload.url)
        status_store.mark_failed(repo_id, reason=str(exc) or exc.__class__.__name__)
        raise HTTPException(status_code=500, detail="Failed to enqueue repository job")

    return _record_to_summary(record)


@router.get("/repo", response_model=List[RepoSummary])
async def list_repositories(
    status_store: RepoStatusStore = Depends(get_status_store),
    settings: ApiSettings = Depends(get_settings),
    reader: SnippetVectorReader = Depends(get_vector_reader),
) -> List[RepoSummary]:
    records = status_store.list_records()

    summaries: List[RepoSummary] = []
    summary_index: dict[str, int] = {}
    for record in records:
        summary = _record_to_summary(record)
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


@router.get("/repo/{repo_id}", response_model=RepoDetailResponse)
async def get_repository(
    repo_id: str,
    status_store: RepoStatusStore = Depends(get_status_store),
    reader: SnippetVectorReader = Depends(get_vector_reader),
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

    summary = _record_to_summary(record)
    return RepoDetailResponse(
        **summary.model_dump(),
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        snippet_count=snippet_count,
    )


@router.get("/snippets", response_model=SnippetQueryResponse)
async def query_snippets(
    query: str = Query(..., min_length=1, description="Natural language search query"),
    limit: int = Query(5, ge=1, le=50, description="Maximum number of snippets to return"),
    reader: SnippetVectorReader = Depends(get_vector_reader),
) -> SnippetQueryResponse:
    try:
        snippets = reader.query(query, limit=limit)
    except Exception as exc:  # pragma: no cover - embed/search errors
        logger.exception("Snippet query failed")
        raise HTTPException(status_code=500, detail=f"Snippet query failed: {exc}") from exc

    results = [SnippetResponse.from_snippet(snippet) for snippet in snippets]
    return SnippetQueryResponse(query=query, results=results)


# Helpers ---------------------------------------------------------------------


def _record_to_summary(record: RepoRecord) -> RepoSummary:
    return RepoSummary(
        id=record.id,
        url=record.url,
        repo_name=record.repo_name,
        status=record.status,
        process_message=record.process_message,
        fail_reason=record.fail_reason,
        progress=record.progress,
    )


def _derive_repo_name(url: str | None) -> str | None:
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

__all__ = ["router", "ApiSettings"]
