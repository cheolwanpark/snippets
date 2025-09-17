from __future__ import annotations

import logging
from typing import List, Sequence

from qdrant_client import QdrantClient, models

from ..snippet import Snippet
from .config import DBConfig, EmbeddingConfig
from .embedding import GeminiEmbeddingClient

logger = logging.getLogger("snippet_extractor")

REQUIRED_SNIPPET_FIELDS = ("title", "description", "language", "code", "path")


class SnippetVectorReader:
    """Query snippets stored in Qdrant using Gemini embeddings and MMR search."""

    def __init__(
        self,
        db_config: DBConfig,
        embedding_config: EmbeddingConfig,
        *,
        lambda_coef: float = 0.7,
    ) -> None:
        self.db_config = db_config
        self.collection_name = db_config.collection_name
        self.lambda_coef = lambda_coef

        self._client = QdrantClient(**db_config.client_kwargs())
        self._embedder = GeminiEmbeddingClient(embedding_config)

    def query(
        self,
        query_text: str,
        *,
        limit: int = 5,
        query_filter: models.Filter | None = None,
    ) -> List[Snippet]:
        """Run an MMR search against the stored snippets."""
        if not query_text.strip():
            return []
        if limit <= 0:
            return []

        vectors = self._embedder.embed([query_text])
        if not vectors:
            logger.warning("Failed to generate embedding for query text")
            return []
        query_vector = vectors[0]

        try:
            results = self._client.mmr(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                lambda_coef=self.lambda_coef,
                filter=query_filter,
                with_payload=True,
            )
        except AttributeError:
            logger.warning(
                "Installed qdrant-client does not expose MMR API; falling back to standard search",
            )
            results = None
        except Exception as exc:  # pragma: no cover - degraded path when MMR fails
            logger.warning(
                "Qdrant MMR search raised %s; falling back to standard search", exc.__class__.__name__
            )
            results = None

        if results is None:
            results = self._client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )

        return self._parse_results(results)

    @staticmethod
    def _parse_results(points: Sequence[models.ScoredPoint]) -> List[Snippet]:
        snippets: List[Snippet] = []
        for point in points:
            payload = getattr(point, "payload", None)
            if not isinstance(payload, dict):
                continue

            snippet_data: dict[str, object] = {}
            missing_field = False
            for field in REQUIRED_SNIPPET_FIELDS:
                value = payload.get(field)
                if value is None:
                    missing_field = True
                    break
                snippet_data[field] = value

            if missing_field:
                logger.debug("Skipping point %s due to missing fields", getattr(point, "id", "?"))
                continue

            if "repo" in payload:
                snippet_data["repo"] = payload["repo"]

            try:
                snippets.append(Snippet(**snippet_data))
            except Exception as exc:  # pragma: no cover - pydantic validation safety net
                logger.debug("Failed to hydrate Snippet from payload %s: %s", payload, exc)

        return snippets


__all__ = ["SnippetVectorReader"]
