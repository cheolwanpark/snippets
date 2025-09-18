"""Quick script to exercise list_repositories without FastAPI wiring."""

from __future__ import annotations

import asyncio
import datetime
from typing import Iterable

from src.api.routes import ApiSettings, list_repositories
from src.vectordb.reader import RepoMetadata
from src.worker.status import RepoRecord, STATUS_PROCESSING


class _StubStatusStore:
    def __init__(self, records: Iterable[RepoRecord]) -> None:
        self._records = list(records)

    def list_records(self) -> list[RepoRecord]:
        return list(self._records)


class _StubReader:
    def __init__(self, metadata: Iterable[RepoMetadata]) -> None:
        self._metadata = list(metadata)

    def list_completed_repositories(self, *, limit: int, exclude_ids=None):
        print(f"list_completed_repositories called with limit={limit}")
        return list(self._metadata)


def _make_settings() -> ApiSettings:
    return ApiSettings(
        redis_url="redis://localhost:6379/0",
        queue_name="repo-ingest",
        queue_default_timeout=1800,
        queue_result_ttl=None,
        status_ttl=None,
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
        qdrant_collection="snippet_embeddings",
        qdrant_facet_limit=100,
        embedding_model="text-embedding-004",
        embedding_api_key=None,
        embedding_batch_size=100,
        embedding_output_dim=None,
    )


async def _run_demo() -> None:
    processing = RepoRecord(
        id="processing-1",
        url="https://github.com/example/processing",
        status=STATUS_PROCESSING,
        repo_name="example/processing",
        process_message="Working",
        fail_reason=None,
        progress=25,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )

    completed = RepoMetadata(
        ingest_id="completed-1",
        repo_url="https://github.com/example/completed",
        repo_name="example/completed",
    )

    summaries = await list_repositories(
        status_store=_StubStatusStore([processing]),
        settings=_make_settings(),
        reader=_StubReader([completed]),
    )

    print("\nSummaries returned by list_repositories:\n")
    for summary in summaries:
        print(summary.model_dump())


if __name__ == "__main__":
    asyncio.run(_run_demo())
