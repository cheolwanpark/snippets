"""Demonstrate SnippetVectorReader fallback when Qdrant facets and grouping are unavailable."""

from __future__ import annotations

from dataclasses import dataclass

from src.vectordb.config import DBConfig, EmbeddingConfig
from src.vectordb.reader import RepoMetadata, SnippetVectorReader


@dataclass
class _Point:
    payload: dict[str, object]


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.scroll_invocations = 0

    def facet(self, **_kwargs):  # mimic old client without facet support
        raise AttributeError("facet not available")

    def query_points_groups(self, **_kwargs):  # mimic client without grouping
        raise RuntimeError("grouping not supported")

    def scroll(self, **kwargs):
        self.scroll_invocations += 1
        print(f"scroll called with limit={kwargs.get('limit')} offset={kwargs.get('offset')}")
        if kwargs.get("filter") or kwargs.get("scroll_filter"):
            ingest_id = kwargs.get("filter").must[0].match.value  # type: ignore[union-attr]
            return [
                _Point(
                    {
                        "ingest_id": ingest_id,
                        "repo_url": f"https://github.com/example/{ingest_id}",
                        "repo_name": ingest_id.replace('-', '/'),
                    }
                )
            ], None
        if self.scroll_invocations == 1:
            return [
                _Point(
                    {
                        "ingest_id": "job-a",
                        "repo_url": "https://github.com/example/completed-a",
                        "repo_name": "example/completed-a",
                    }
                ),
                _Point(
                    {
                        "ingest_id": "job-b",
                        "repo_url": "https://github.com/example/completed-b",
                        "repo_name": "example/completed-b",
                    }
                ),
            ], None
        return [], None


def main() -> None:
    reader = SnippetVectorReader(
        DBConfig(collection_name="demo"),
        EmbeddingConfig(model="text-embedding-004"),
    )
    reader._client = _FakeQdrantClient()  # type: ignore[attr-defined]

    metadata = reader.list_completed_repositories(limit=5)

    print("\nMetadata entries discovered via scroll fallback:\n")
    for entry in metadata:
        assert isinstance(entry, RepoMetadata)
        print(entry)


if __name__ == "__main__":
    main()
