"""FastAPI routes for repository ingestion and snippet search."""

from __future__ import annotations

from typing import List

import redis
from fastapi import APIRouter, Depends, Query, Request, Response, status
from rq import Queue

from ..vectordb.config import DBConfig, EmbeddingConfig
from ..vectordb.reader import SnippetVectorReader
from ..vectordb.writer import SnippetVectorWriter
from ..worker.queue import QueueConfig, create_queue
from ..worker.status import RepoStatusStore
from .model import (
    RepoCreateRequest,
    RepoCreateResponse,
    RepoDetailResponse,
    RepoSummary,
    SnippetQueryResponse,
)
from .service import (
    ApiSettings,
    delete_repository_service,
    enqueue_repository_service,
    get_repository_service,
    list_repositories_service,
    query_snippets_service,
)


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


def _build_vector_configs(settings: ApiSettings) -> tuple[DBConfig, EmbeddingConfig]:
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
    return db_config, embedding_config


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
        db_config, embedding_config = _build_vector_configs(settings)
        reader = SnippetVectorReader(db_config, embedding_config)
        request.app.state.vector_reader = reader
    return reader


def get_vector_writer(
    request: Request,
    settings: ApiSettings = Depends(get_settings),
) -> SnippetVectorWriter:
    writer = getattr(request.app.state, "vector_writer", None)
    if writer is None:
        db_config, embedding_config = _build_vector_configs(settings)
        writer = SnippetVectorWriter(db_config, embedding_config)
        request.app.state.vector_writer = writer
    return writer


router = APIRouter()


@router.post("/repo", response_model=RepoCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_repository(
    payload: RepoCreateRequest,
    queue: Queue = Depends(get_queue),
    status_store: RepoStatusStore = Depends(get_status_store),
    settings: ApiSettings = Depends(get_settings),
    vector_writer: SnippetVectorWriter = Depends(get_vector_writer),
) -> RepoCreateResponse:
    return enqueue_repository_service(
        payload,
        queue,
        status_store,
        settings,
        vector_writer=vector_writer,
    )


@router.get("/repo", response_model=List[RepoSummary])
async def list_repositories(
    status_store: RepoStatusStore = Depends(get_status_store),
    settings: ApiSettings = Depends(get_settings),
    reader: SnippetVectorReader = Depends(get_vector_reader),
) -> List[RepoSummary]:
    return list_repositories_service(status_store, reader, settings)


@router.get("/repo/{repo_id}", response_model=RepoDetailResponse)
async def get_repository(
    repo_id: str,
    status_store: RepoStatusStore = Depends(get_status_store),
    reader: SnippetVectorReader = Depends(get_vector_reader),
) -> RepoDetailResponse:
    return get_repository_service(repo_id, status_store, reader)


@router.delete(
    "/repo/{repo_id}",
    response_class=Response,
)
async def delete_repository(
    repo_id: str,
    status_store: RepoStatusStore = Depends(get_status_store),
    queue: Queue = Depends(get_queue),
    vector_writer: SnippetVectorWriter = Depends(get_vector_writer),
) -> Response:
    """Delete a repository ingest and its resources."""

    delete_repository_service(repo_id, status_store, queue, vector_writer)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/snippets", response_model=SnippetQueryResponse)
async def query_snippets(
    query: str = Query(..., min_length=1, description="Natural language search query"),
    limit: int = Query(5, ge=1, le=50, description="Maximum number of snippets to return"),
    reader: SnippetVectorReader = Depends(get_vector_reader),
    repo_name: str | None = Query(None, description="Filter results to a specific repository"),
    language: str | None = Query(None, description="Filter results to a language code"),
) -> SnippetQueryResponse:
    return query_snippets_service(
        query,
        limit,
        reader,
        repo_name=repo_name,
        language=language,
    )


__all__ = ["router"]
