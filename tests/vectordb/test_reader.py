import pytest

from src.vectordb.config import DBConfig, EmbeddingConfig
from src.vectordb.reader import RepoMetadata, SnippetVectorReader


class _Point:
    def __init__(self, payload):
        self.payload = payload


class _FakeQdrantClient:
    def __init__(self):
        self.scroll_calls = []

    def facet(self, **_kwargs):  # pragma: no cover - intentionally unused
        raise AttributeError("facet unsupported")

    def query_points_groups(self, **_kwargs):  # pragma: no cover - intentionally unused
        raise RuntimeError("grouping unsupported")

    def scroll(self, **kwargs):
        self.scroll_calls.append(kwargs)
        if len(self.scroll_calls) == 1:
            points = [
                _Point(
                    {
                        "ingest_id": "job-a",
                        "repo_url": "https://example.com/job-a",
                        "repo_name": "job/a",
                    }
                ),
                _Point(
                    {
                        "ingest_id": "job-b",
                        "repo_url": "https://example.com/job-b",
                        "repo_name": "job/b",
                    }
                ),
            ]
            return points, None
        return [], None


@pytest.fixture(autouse=True)
def _patch_qdrant_client(monkeypatch):
    fake_client = _FakeQdrantClient()
    monkeypatch.setattr("src.vectordb.reader.QdrantClient", lambda **_kwargs: fake_client)
    return fake_client


def _make_reader():
    db_config = DBConfig(url=None, api_key=None, collection_name="test")
    embedding_config = EmbeddingConfig(api_key=None, model="test")
    return SnippetVectorReader(db_config, embedding_config)


@pytest.mark.asyncio
async def test_scroll_fallback_returns_completed_metadata():
    reader = _make_reader()

    results = reader.list_completed_repositories(limit=5)

    assert [metadata.ingest_id for metadata in results] == ["job-a", "job-b"]
    assert all(isinstance(metadata, RepoMetadata) for metadata in results)
