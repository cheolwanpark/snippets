from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Sequence, Set

from qdrant_client import QdrantClient, models

from ..snippet import Snippet
from .config import DBConfig, EmbeddingConfig
from .embedding import GeminiEmbeddingClient

logger = logging.getLogger("snippet_extractor")

REQUIRED_SNIPPET_FIELDS = ("title", "description", "language", "code", "path")


@dataclass(frozen=True, slots=True)
class RepoMetadata:
    """Metadata about a completed repository ingest stored in Qdrant."""

    ingest_id: str
    repo_url: str
    repo_name: str | None
    snippet_count: int | None = None


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
        self._embedding_config = embedding_config
        self._embedder: GeminiEmbeddingClient | None = None

    def query(
        self,
        query_text: str,
        *,
        limit: int = 5,
        repo_name: str | None = None,
        language: str | None = None,
    ) -> List[Snippet]:
        """Run an MMR search against the stored snippets."""
        if not query_text.strip():
            return []
        if limit <= 0:
            return []

        embedder = self._get_embedder()
        vectors = embedder.embed([query_text])
        if not vectors:
            logger.warning("Failed to generate embedding for query text")
            return []
        query_vector = vectors[0]

        combined_filter = self._combine_filters(
            repo_name=repo_name,
            language=language,
        )

        try:
            results = self._client.mmr(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                lambda_coef=self.lambda_coef,
                filter=combined_filter,
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
                query_filter=combined_filter,
                limit=limit,
                with_payload=True,
            )

        return self._parse_results(results)

    def list_completed_repositories(
        self,
        *,
        limit: int,
        exclude_ids: Set[str] | None = None,
    ) -> List[RepoMetadata]:
        """Return completed ingest records stored in Qdrant."""
        ingest_ids = self._list_completed_ingest_ids(limit)
        if not ingest_ids:
            return []

        excluded = exclude_ids or set()
        metadata: List[RepoMetadata] = []
        for ingest_id in ingest_ids:
            if not ingest_id or ingest_id in excluded:
                continue

            payload = self._load_completed_repo_metadata(ingest_id)
            if not payload:
                logger.debug("Skipping ingest_id %s without payload", ingest_id)
                continue

            repo_url = _coerce_repo_url(payload)
            if not repo_url:
                logger.debug("Skipping ingest_id %s without repo_url", ingest_id)
                continue

            repo_name = _coerce_repo_name(payload)
            metadata.append(
                RepoMetadata(
                    ingest_id=ingest_id,
                    repo_url=repo_url,
                    repo_name=repo_name,
                )
            )

        return metadata

    def get_completed_repository(self, ingest_id: str) -> RepoMetadata | None:
        """Fetch metadata and snippet count for a completed ingest."""
        payload = self._load_completed_repo_metadata(ingest_id)
        if not payload:
            return None

        repo_url = _coerce_repo_url(payload)
        if not repo_url:
            return None

        repo_name = _coerce_repo_name(payload)
        snippet_count = self._count_snippets_for_ingest(ingest_id)
        return RepoMetadata(
            ingest_id=ingest_id,
            repo_url=repo_url,
            repo_name=repo_name,
            snippet_count=snippet_count,
        )

    def count_snippets_for_repo(self, repo_name: str) -> int | None:
        """Count the number of snippets stored for a repository."""
        try:
            filter_ = models.Filter(
                must=[
                    models.FieldCondition(
                        key="repo_name",
                        match=models.MatchValue(value=repo_name),
                    )
                ]
            )
            result = self._client.count(
                collection_name=self.collection_name,
                filter=filter_,
                exact=False,
            )
            return getattr(result, "count", None)
        except Exception:
            logger.debug("Failed to count snippets for repo %s", repo_name, exc_info=True)
            return None

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

            repo = payload.get("repo")
            if repo is not None:
                snippet_data["repo"] = repo

            repo_name = payload.get("repo_name")
            if repo_name is not None:
                snippet_data["repo_name"] = repo_name
                snippet_data.setdefault("repo", repo_name)

            repo_url = payload.get("repo_url")
            if repo_url is not None:
                snippet_data["repo_url"] = repo_url

            ingest_id = payload.get("ingest_id")
            if ingest_id is not None:
                snippet_data["ingest_id"] = ingest_id

            try:
                snippets.append(Snippet(**snippet_data))
            except Exception as exc:  # pragma: no cover - pydantic validation safety net
                logger.debug("Failed to hydrate Snippet from payload %s: %s", payload, exc)

        return snippets

    def _get_embedder(self) -> GeminiEmbeddingClient:
        if self._embedder is None:
            self._embedder = GeminiEmbeddingClient(self._embedding_config)
        return self._embedder

    def _combine_filters(
        self,
        *,
        repo_name: str | None,
        language: str | None,
    ) -> models.Filter | None:
        conditions: list[models.FieldCondition] = []

        if repo_name and repo_name.strip():
            conditions.append(
                models.FieldCondition(
                    key="repo_name",
                    match=models.MatchValue(value=repo_name.strip()),
                )
            )

        if language and language.strip():
            conditions.append(
                models.FieldCondition(
                    key="language",
                    match=models.MatchValue(value=language.strip()),
                )
            )

        if not conditions:
            return None

        return models.Filter(must=conditions)

    def _list_completed_ingest_ids(self, limit: int) -> List[str]:
        if limit <= 0:
            limit = 100
        ingest_ids = self._facet_ingest_ids(limit)
        if ingest_ids:
            return ingest_ids

        ingest_ids = self._group_ingest_ids(limit)
        if ingest_ids:
            return ingest_ids

        return self._scroll_ingest_ids(limit)

    def _facet_ingest_ids(self, limit: int) -> List[str]:
        try:
            facet = self._client.facet(
                collection_name=self.collection_name,
                key="ingest_id",
                limit=limit,
                exact=False,
            )
            hits_container = getattr(facet, "result", facet)
            hits = getattr(hits_container, "hits", [])
            ingest_ids = [str(hit.value) for hit in hits if getattr(hit, "value", None)]
            return ingest_ids
        except AttributeError:
            pass
        except Exception:
            logger.debug("Facet ingest_id lookup failed", exc_info=True)

        return []

    def _group_ingest_ids(self, limit: int) -> List[str]:
        try:
            groups = self._client.query_points_groups(
                collection_name=self.collection_name,
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

    def _scroll_ingest_ids(self, limit: int) -> List[str]:
        logger.debug("Falling back to scroll for ingest_id discovery")
        ingest_ids: List[str] = []
        seen: set[str] = set()
        next_page: object | None = None

        batch_size = max(1, min(limit * 2, 256))

        while True:
            scroll_kwargs = {
                "collection_name": self.collection_name,
                "limit": batch_size,
                "with_payload": True,
                "with_vectors": False,
            }
            if next_page:
                scroll_kwargs["offset"] = next_page

            try:
                result = self._client.scroll(**scroll_kwargs)
            except TypeError:
                result = self._client.scroll(scroll_filter=None, **scroll_kwargs)
            except AttributeError:
                logger.debug("Scroll ingest_id lookup unsupported", exc_info=True)
                return ingest_ids
            except Exception:
                logger.debug("Scroll ingest_id lookup failed", exc_info=True)
                return ingest_ids

            points, next_page = self._unpack_scroll_result(result)
            if not points:
                break

            for payload in points:
                ingest_id = payload.get("ingest_id")
                if not ingest_id:
                    continue
                ident = str(ingest_id)
                if ident in seen:
                    continue
                seen.add(ident)
                ingest_ids.append(ident)
                if 0 < limit <= len(ingest_ids):
                    return ingest_ids

            if not next_page:
                break

        return ingest_ids

    @staticmethod
    def _unpack_scroll_result(result: Any) -> tuple[List[dict[str, Any]], Any]:
        points = result
        next_page = None

        if isinstance(result, tuple):
            points, next_page = result
        else:
            next_page = getattr(result, "next_page_offset", None)

        if hasattr(points, "points"):
            next_page = getattr(points, "next_page_offset", next_page)
            points = getattr(points, "points")
        if hasattr(points, "records"):
            next_page = getattr(points, "next_page_offset", next_page)
            points = getattr(points, "records")

        payloads: List[dict[str, Any]] = []
        for point in points or []:
            payload = getattr(point, "payload", None)
            if isinstance(payload, dict):
                payloads.append(payload)

        return payloads, next_page

    def _load_completed_repo_metadata(self, ingest_id: str) -> dict[str, Any] | None:
        filter_ = models.Filter(
            must=[
                models.FieldCondition(
                    key="ingest_id",
                    match=models.MatchValue(value=ingest_id),
                ),
            ]
        )
        scroll_kwargs = {
            "collection_name": self.collection_name,
            "limit": 1,
            "with_payload": True,
            "with_vectors": False,
        }
        try:
            scroll_result = self._client.scroll(filter=filter_, **scroll_kwargs)
        except (TypeError, AssertionError):
            scroll_result = self._client.scroll(scroll_filter=filter_, **scroll_kwargs)
        except AttributeError:
            return None
        except Exception:
            logger.debug(
                "Failed to scroll for ingest_id %s", ingest_id, exc_info=True
            )
            return None

        return self._first_payload(scroll_result)

    def _count_snippets_for_ingest(self, ingest_id: str) -> int | None:
        try:
            filter_ = models.Filter(
                must=[
                    models.FieldCondition(
                        key="ingest_id",
                        match=models.MatchValue(value=ingest_id),
                    ),
                ]
            )
            result = self._client.count(
                collection_name=self.collection_name,
                filter=filter_,
                exact=False,
            )
            return getattr(result, "count", None)
        except Exception:
            logger.debug("Failed to count snippets for ingest %s", ingest_id, exc_info=True)
            return None

    @staticmethod
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


def _coerce_repo_url(payload: dict[str, Any]) -> str | None:
    raw_url = payload.get("repo_url") or payload.get("repo")
    if not raw_url:
        return None
    try:
        return str(raw_url)
    except Exception:
        logger.debug("Invalid repo_url payload value: %r", raw_url, exc_info=True)
        return None


def _coerce_repo_name(payload: dict[str, Any]) -> str | None:
    repo_name = payload.get("repo_name") or payload.get("repo")
    if not repo_name:
        return None
    try:
        coerced = str(repo_name)
    except Exception:
        logger.debug("Invalid repo_name payload value: %r", repo_name, exc_info=True)
        return None
    return coerced or None


__all__ = ["SnippetVectorReader", "RepoMetadata"]
