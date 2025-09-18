"""FastAPI routes for repository ingestion and snippet search."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, List, Sequence, Set

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models
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


def _get_qdrant_client(request: Request, settings: ApiSettings) -> QdrantClient:
    client = getattr(request.app.state, "qdrant_client", None)
    if client is None:
        client_kwargs: dict[str, Any] = {}
        if settings.qdrant_url:
            client_kwargs["url"] = settings.qdrant_url
        if settings.qdrant_api_key:
            client_kwargs["api_key"] = settings.qdrant_api_key
        client = QdrantClient(**client_kwargs)
        request.app.state.qdrant_client = client
    return client


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
    request: Request,
    status_store: RepoStatusStore = Depends(get_status_store),
    settings: ApiSettings = Depends(get_settings),
) -> List[RepoSummary]:
    records = status_store.list_records()
    summaries = [_record_to_summary(record) for record in records]

    active_ids: Set[str] = {record.id for record in records}

    try:
        qdrant_client = _get_qdrant_client(request, settings)
        completed_summaries = _list_completed_repo_summaries(
            qdrant_client,
            settings.qdrant_collection,
            limit=settings.qdrant_facet_limit,
            exclude_ids=active_ids,
        )
        summaries.extend(completed_summaries)
    except Exception:
        logger.debug("Failed to load completed repositories from Qdrant", exc_info=True)

    return summaries


@router.get("/repo/{repo_id}", response_model=RepoDetailResponse)
async def get_repository(
    repo_id: str,
    request: Request,
    status_store: RepoStatusStore = Depends(get_status_store),
    settings: ApiSettings = Depends(get_settings),
) -> RepoDetailResponse:
    record = status_store.get(repo_id)
    if record is None:
        try:
            qdrant_client = _get_qdrant_client(request, settings)
            completed = _get_completed_repo_detail(
                qdrant_client,
                settings.qdrant_collection,
                repo_id,
            )
        except Exception:
            logger.debug("Failed to fetch completed repository %s", repo_id, exc_info=True)
            completed = None

        if completed is None:
            raise HTTPException(status_code=404, detail="Repository not found")

        summary, snippet_count = completed
        return RepoDetailResponse(
            **summary.model_dump(),
            created_at=None,
            updated_at=None,
            snippet_count=snippet_count,
        )

    snippet_count: int | None = None
    if record.repo_name:
        try:
            qdrant_client = _get_qdrant_client(request, settings)
            snippet_count = _count_snippets_for_repo(
                qdrant_client,
                settings.qdrant_collection,
                record.repo_name,
            )
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


def _list_completed_repo_summaries(
    client: QdrantClient,
    collection: str,
    *,
    limit: int,
    exclude_ids: Set[str],
) -> List[RepoSummary]:
    ingest_ids = _list_completed_ingest_ids(client, collection, limit=limit)
    summaries: List[RepoSummary] = []
    for ingest_id in ingest_ids:
        if not ingest_id or ingest_id in exclude_ids:
            continue
        metadata = _load_completed_repo_metadata(client, collection, ingest_id)
        if not metadata:
            continue
        repo_url = metadata.get("repo_url")
        if not repo_url:
            continue
        repo_name = metadata.get("repo_name") or metadata.get("repo")
        summaries.append(
            RepoSummary(
                id=ingest_id,
                url=str(repo_url),
                repo_name=repo_name if repo_name else None,
                status=STATUS_DONE,
                process_message="Completed",
                fail_reason=None,
                progress=100,
            )
        )
    return summaries


def _list_completed_ingest_ids(
    client: QdrantClient,
    collection: str,
    *,
    limit: int,
) -> List[str]:
    if limit <= 0:
        limit = 100
    try:
        facet = client.facet(collection_name=collection, key="ingest_id", limit=limit, exact=False)
        hits_container = getattr(facet, "result", facet)
        hits = getattr(hits_container, "hits", [])
        ingest_ids = [str(hit.value) for hit in hits if getattr(hit, "value", None)]
        if ingest_ids:
            return ingest_ids
    except AttributeError:
        pass
    except Exception:
        logger.debug("Facet ingest_id lookup failed", exc_info=True)

    try:
        groups = client.query_points_groups(
            collection_name=collection,
            group_by="ingest_id",
            group_size=1,
            limit=limit,
            with_payload=False,
            with_vector=False,
        )
    except Exception:
        logger.debug("Group ingest_id lookup failed", exc_info=True)
        return []

    ingest_ids: List[str] = []
    for group in groups or []:
        group_id = getattr(group, "group_id", None)
        if group_id:
            ingest_ids.append(str(group_id))
    return ingest_ids


def _load_completed_repo_metadata(
    client: QdrantClient,
    collection: str,
    ingest_id: str,
) -> dict[str, Any] | None:
    filter_ = models.Filter(
        must=[
            models.FieldCondition(key="ingest_id", match=models.MatchValue(value=ingest_id)),
        ]
    )
    scroll_kwargs = {
        "collection_name": collection,
        "limit": 1,
        "with_payload": True,
        "with_vectors": False,
    }
    try:
        scroll_result = client.scroll(filter=filter_, **scroll_kwargs)
    except TypeError:
        scroll_result = client.scroll(scroll_filter=filter_, **scroll_kwargs)
    except AttributeError:
        return None
    except Exception:
        logger.debug("Failed to scroll for ingest_id %s", ingest_id, exc_info=True)
        return None

    return _first_payload(scroll_result)


def _first_payload(points_result: Any) -> dict[str, Any] | None:
    points = points_result
    if isinstance(points_result, tuple):
        points = points_result[0]
    if points is None:
        return None
    if hasattr(points, "points"):
        points = getattr(points, "points")
    if hasattr(points, "records"):
        points = getattr(points, "records")
    for point in points or []:
        payload = getattr(point, "payload", None)
        if isinstance(payload, dict):
            return payload
    return None


def _get_completed_repo_detail(
    client: QdrantClient,
    collection: str,
    ingest_id: str,
) -> tuple[RepoSummary, int | None] | None:
    metadata = _load_completed_repo_metadata(client, collection, ingest_id)
    if not metadata:
        return None
    repo_url = metadata.get("repo_url")
    if not repo_url:
        return None
    repo_name = metadata.get("repo_name") or metadata.get("repo")
    summary = RepoSummary(
        id=ingest_id,
        url=str(repo_url),
        repo_name=repo_name if repo_name else None,
        status=STATUS_DONE,
        process_message="Completed",
        fail_reason=None,
        progress=100,
    )
    snippet_count = _count_snippets_for_ingest(client, collection, ingest_id)
    return summary, snippet_count


def _count_snippets_for_ingest(
    client: QdrantClient,
    collection: str,
    ingest_id: str,
) -> int | None:
    try:
        filter_ = models.Filter(
            must=[
                models.FieldCondition(
                    key="ingest_id",
                    match=models.MatchValue(value=ingest_id),
                )
            ]
        )
        result = client.count(
            collection_name=collection,
            filter=filter_,
            exact=False,
        )
        return getattr(result, "count", None)
    except Exception:
        logger.debug("Failed to count snippets for ingest %s", ingest_id, exc_info=True)
        return None


def _count_snippets_for_repo(
    client: QdrantClient,
    collection: str,
    repo_name: str,
) -> int | None:
    try:
        filter_ = models.Filter(
            must=[
                models.FieldCondition(
                    key="repo_name",
                    match=models.MatchValue(value=repo_name),
                )
            ]
        )
        result = client.count(
            collection_name=collection,
            filter=filter_,
            exact=False,
        )
        return getattr(result, "count", None)
    except Exception:
        logger.debug("Failed to count snippets for repo %s", repo_name, exc_info=True)
        return None


__all__ = ["router", "ApiSettings"]
