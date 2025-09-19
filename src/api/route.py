"""FastAPI routes for repository ingestion and snippet search."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query, Request, Response, status
from rq import Queue

from ..vectordb.reader import SnippetVectorReader
from ..vectordb.writer import SnippetVectorWriter
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
    get_queue,
    get_repository_service,
    get_settings,
    get_status_store,
    get_vector_reader,
    get_vector_writer,
    list_repositories_service,
    query_snippets_service,
)


router = APIRouter()


@router.post("/repo", response_model=RepoCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_repository(
    request: Request,
    payload: RepoCreateRequest,
    queue: Queue = Depends(get_queue),
    status_store: RepoStatusStore = Depends(get_status_store),
    settings: ApiSettings = Depends(get_settings),
) -> RepoCreateResponse:
    return enqueue_repository_service(request, payload, queue, status_store, settings)


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
