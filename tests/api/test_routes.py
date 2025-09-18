import datetime

import pytest

from src.api.routes import ApiSettings, list_repositories
from src.vectordb.reader import RepoMetadata
from src.worker.status import RepoRecord, STATUS_DONE, STATUS_PROCESSING


class _StubStatusStore:
    def __init__(self, records):
        self._records = records

    def list_records(self):
        return list(self._records)


class _StubVectorReader:
    def __init__(self, metadata):
        self._metadata = metadata
        self.calls = []

    def list_completed_repositories(self, *, limit, exclude_ids=None):  # pragma: no cover - signature shim
        self.calls.append({"limit": limit, "exclude_ids": exclude_ids})
        return list(self._metadata)


def _make_settings(*, facet_limit: int = 100) -> ApiSettings:
    return ApiSettings(
        redis_url="redis://127.0.0.1:6379/0",
        queue_name="repo-ingest",
        queue_default_timeout=1800,
        queue_result_ttl=None,
        status_ttl=None,
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
        qdrant_collection="snippet_embeddings",
        qdrant_facet_limit=facet_limit,
        embedding_model="text-embedding-004",
        embedding_api_key=None,
        embedding_batch_size=100,
        embedding_output_dim=None,
    )


@pytest.mark.asyncio
async def test_list_repositories_includes_completed_metadata():
    repo_id = "processing-1"
    record = RepoRecord(
        id=repo_id,
        url="https://github.com/example/processing",
        status=STATUS_PROCESSING,
        repo_name="example/processing",
        process_message="Working",
        progress=10,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )

    status_store = _StubStatusStore([record])
    reader = _StubVectorReader(
        [
            RepoMetadata(
                ingest_id="completed-1",
                repo_url="https://github.com/example/completed",
                repo_name="example/completed",
            )
        ]
    )

    settings = _make_settings()

    summaries = await list_repositories(status_store=status_store, settings=settings, reader=reader)

    assert {summary.id for summary in summaries} == {repo_id, "completed-1"}
    completed_summary = next(summary for summary in summaries if summary.id == "completed-1")
    assert completed_summary.status == STATUS_DONE
    assert completed_summary.process_message == "Completed"
    assert completed_summary.progress == 100


@pytest.mark.asyncio
async def test_list_repositories_overrides_existing_entry_with_completed_metadata():
    repo_id = "shared-id"
    record = RepoRecord(
        id=repo_id,
        url="https://github.com/example/shared",
        status=STATUS_PROCESSING,
        repo_name="example/shared",
        process_message="Working",
        progress=60,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )

    status_store = _StubStatusStore([record])
    reader = _StubVectorReader(
        [
            RepoMetadata(
                ingest_id=repo_id,
                repo_url="https://github.com/example/shared",
                repo_name="example/shared",
            )
        ]
    )

    settings = _make_settings()

    summaries = await list_repositories(status_store=status_store, settings=settings, reader=reader)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.id == repo_id
    assert summary.status == STATUS_DONE
    assert summary.progress == 100
    assert summary.fail_reason is None
    assert summary.process_message == "Completed"
