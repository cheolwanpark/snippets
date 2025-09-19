from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Sequence

from qdrant_client import QdrantClient, models
try:  # qdrant-client >=1.4 exposes typed HTTP exceptions
    from qdrant_client.http.exceptions import UnexpectedResponse as QdrantUnexpectedResponse  # type: ignore
except Exception:  # pragma: no cover - best effort compatibility with older clients
    QdrantUnexpectedResponse = None  # type: ignore

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
        self._embedding_config = embedding_config
        self._embedder: GeminiEmbeddingClient | None = None

    def write(self, snippets: Sequence[Snippet]) -> int:
        """Upsert snippets into Qdrant. Returns number of points written."""
        snippet_list = list(snippets)
        if not snippet_list:
            return 0

        embedding_inputs = [self._embedding_input(snippet) for snippet in snippet_list]
        embedder = self._get_embedder()
        vectors = embedder.embed(embedding_inputs)

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

    def delete_repository(
        self,
        *,
        ingest_id: str | None = None,
        repo_name: str | None = None,
        repo_url: str | None = None,
    ) -> int:
        """Delete all vectors associated with a repository ingest."""

        # If the collection doesn't exist yet (first run), treat as no-op.
        if not self._collection_exists():
            logger.debug(
                "Qdrant collection %s does not exist; nothing to delete",
                self.collection_name,
            )
            return 0

        conditions: list[models.FieldCondition] = []
        if ingest_id:
            conditions.append(
                models.FieldCondition(
                    key="ingest_id",
                    match=models.MatchValue(value=ingest_id),
                )
            )
        if repo_name:
            conditions.append(
                models.FieldCondition(
                    key="repo_name",
                    match=models.MatchValue(value=repo_name),
                )
            )
        if repo_url:
            conditions.append(
                models.FieldCondition(
                    key="repo_url",
                    match=models.MatchValue(value=repo_url),
                )
            )

        if not conditions:
            raise ValueError("At least one identifier must be provided to delete a repository")

        filter_ = models.Filter(must=conditions)
        delete_kwargs = {
            "collection_name": self.collection_name,
            "wait": True,
        }

        try:
            result = self._client.delete(
                points_selector=models.FilterSelector(filter=filter_),
                **delete_kwargs,
            )
        except TypeError as exc:
            if "points_selector" not in str(exc):
                raise
            # Fallback for legacy qdrant-client versions expecting `filter` kwarg
            result = self._client.delete(filter=filter_, **delete_kwargs)
        except Exception as exc:
            # If the collection was dropped between the existence check and delete,
            # gracefully treat 404 as a no-op instead of failing the request.
            if QdrantUnexpectedResponse is not None and isinstance(exc, QdrantUnexpectedResponse):  # type: ignore[arg-type]
                text = str(exc)
                if "404" in text or "Not found" in text:
                    logger.debug(
                        "Qdrant delete saw 404 for collection %s; nothing to delete",
                        self.collection_name,
                    )
                    return 0
            logger.exception("Failed to delete repository payload from Qdrant")
            raise

        return self._extract_deleted_count(result)

    def _ensure_collection(self, vector_size: int) -> None:
        if not self._collection_exists():
            logger.info(
                "Creating Qdrant collection %s with vector size %d",
                self.collection_name,
                vector_size,
            )
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=self.distance),
            )

        self._ensure_payload_indexes()

    def _collection_exists(self) -> bool:
        """Best-effort way to check collection existence across client versions."""
        try:
            return bool(self._client.collection_exists(self.collection_name))
        except AttributeError:
            # Older clients may not expose collection_exists; fall back to get_collection
            try:
                self._client.get_collection(self.collection_name)
                return True
            except Exception:
                return False

    def _ensure_payload_indexes(self) -> None:
        """Ensure payload indexes needed for metadata querying exist."""
        try:
            self._client.create_payload_index(
                collection_name=self.collection_name,
                field_name="repo_name",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:  # pragma: no cover - best effort guard
            logger.debug("Skipping repo_name index creation: %s", exc)

        try:
            self._client.create_payload_index(
                collection_name=self.collection_name,
                field_name="ingest_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:  # pragma: no cover - best effort guard
            logger.debug("Skipping ingest_id index creation: %s", exc)

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
        if language := payload.get("language"):
            payload["language"] = language.lower()
        payload["embedding_input"] = embedding_input
        payload["embedding_key"] = embedding_key
        return payload

    def _get_embedder(self) -> GeminiEmbeddingClient:
        if self._embedder is None:
            self._embedder = GeminiEmbeddingClient(self._embedding_config)
        return self._embedder

    @staticmethod
    def _extract_deleted_count(result: object) -> int:
        if result is None:
            return 0

        target = getattr(result, "result", result)
        count = getattr(target, "count", None)
        if count is None:
            count = getattr(target, "deleted_count", None)

        try:
            return int(count) if count is not None else 0
        except (TypeError, ValueError):
            logger.debug("Unable to coerce deleted count from Qdrant response", exc_info=True)
            return 0


__all__ = ["SnippetVectorWriter"]
