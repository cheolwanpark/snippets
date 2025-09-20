from __future__ import annotations

import logging
import os
from typing import List, Sequence
import cohere

from ..snippet import Snippet


logger = logging.getLogger("snippet_extractor")


class Reranker:
    """Order snippets by semantic relevance using Cohere's rerank API."""

    DEFAULT_MODEL = "rerank-v3.5"

    def __init__(self, model: str | None = None) -> None:
        api_key = os.environ.get("COHERE_API_KEY", None)
        if not api_key:
            raise RuntimeError("COHERE_API_KEY is not set")

        self._client = cohere.ClientV2(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    @classmethod
    def is_available(cls) -> bool:
        return bool(os.environ.get("COHERE_API_KEY")) and cohere is not None

    def rerank(self, query: str, snippets: Sequence[Snippet]) -> List[Snippet]:
        if not query.strip():
            return list(snippets)
        if not snippets:
            return []

        documents = [self._serialize(snippet) for snippet in snippets]

        try:
            response = self._client.rerank(
                model=self._model,
                query=query,
                documents=documents
            )
        except Exception:  # pragma: no cover - network/runtime failures
            logger.exception("Cohere rerank request failed")
            return list(snippets)

        results = response.results
        if not results:
            logger.debug("Cohere rerank returned no results")
            return list(snippets)

        ordered: List[Snippet] = []
        for item in results:
            ordered.append(snippets[item.index])

        return ordered

    @staticmethod
    def _serialize(snippet: Snippet) -> str:
        title = snippet.title.strip()
        description = snippet.description.strip()
        if title and description:
            return f"{title}\n\n{description}"
        return title or description
