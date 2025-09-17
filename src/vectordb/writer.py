from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Sequence

from qdrant_client import QdrantClient, models

from ..snippet import Snippet
from .config import DBConfig, EmbeddingConfig
from .embedding import GeminiEmbeddingClient

logger = logging.getLogger("snippet_extractor")


class SnippetVectorWriter:
    """Persist snippets and their embeddings into a Qdrant collection."""

    def __init__(
        self,
        db_config: DBConfig,
        embedding_config: EmbeddingConfig,
        *,
        distance: models.Distance = models.Distance.COSINE,
    ) -> None:
        self.db_config = db_config
        self.collection_name = db_config.collection_name
        self.distance = distance

        self._client = QdrantClient(**db_config.client_kwargs())
        self._embedder = GeminiEmbeddingClient(embedding_config)

    def write(self, snippets: Sequence[Snippet]) -> int:
        """Upsert snippets into Qdrant. Returns number of points written."""
        snippet_list = list(snippets)
        if not snippet_list:
            return 0

        embedding_inputs = [self._embedding_input(snippet) for snippet in snippet_list]
        vectors = self._embedder.embed(embedding_inputs)

        if len(vectors) != len(snippet_list):
            logger.error(
                "Mismatch between snippet count (%d) and embeddings returned (%d)",
                len(snippet_list),
                len(vectors),
            )
            limit = min(len(snippet_list), len(vectors))
            snippet_list = snippet_list[:limit]
            vectors = vectors[:limit]
            embedding_inputs = embedding_inputs[:limit]

        if not vectors:
            logger.warning("No vectors produced for %d snippets", len(embedding_inputs))
            return 0

        vector_size = len(vectors[0])
        self._ensure_collection(vector_size)

        if not vectors:
            return 0

        total_written = 0
        batch_size = max(1, self.db_config.upsert_batch_size)

        for start in range(0, len(snippet_list), batch_size):
            snippet_batch = snippet_list[start : start + batch_size]
            input_batch = embedding_inputs[start : start + batch_size]
            vector_batch = vectors[start : start + batch_size]

            points: list[models.PointStruct] = []
            for snippet, vector, embedding_input in zip(snippet_batch, vector_batch, input_batch):
                embedding_key = self._embedding_key(embedding_input)
                payload = self._build_payload(snippet, embedding_input, embedding_key)
                points.append(
                    models.PointStruct(
                        id=self._point_id(embedding_input),
                        vector=vector,
                        payload=payload,
                    )
                )

            if not points:
                continue

            self._client.upsert(collection_name=self.collection_name, points=points)
            total_written += len(points)

        return total_written

    def _ensure_collection(self, vector_size: int) -> None:
        try:
            exists = self._client.collection_exists(self.collection_name)
        except AttributeError:
            try:
                self._client.get_collection(self.collection_name)
                return
            except Exception:  # pragma: no cover - defensive fall back
                exists = False
        if exists:
            return

        logger.info(
            "Creating Qdrant collection %s with vector size %d",
            self.collection_name,
            vector_size,
        )
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=self.distance),
        )

    @staticmethod
    def _embedding_input(snippet: Snippet) -> str:
        return f"{snippet.title}\n\n{snippet.description}"

    @staticmethod
    def _embedding_key(embedding_input: str) -> str:
        return hashlib.sha256(embedding_input.encode("utf-8")).hexdigest()

    @staticmethod
    def _point_id(embedding_input: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, embedding_input))

    @staticmethod
    def _build_payload(
        snippet: Snippet,
        embedding_input: str,
        embedding_key: str,
    ) -> dict[str, object]:
        payload = snippet.model_dump(exclude_none=True)
        payload["embedding_input"] = embedding_input
        payload["embedding_key"] = embedding_key
        return payload


__all__ = ["SnippetVectorWriter"]
