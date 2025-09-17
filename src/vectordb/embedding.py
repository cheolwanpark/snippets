from __future__ import annotations

import logging
import os
from typing import Any, List, MutableMapping, Sequence

from google import genai
from google.genai import types

from .config import EmbeddingConfig

logger = logging.getLogger("snippet_extractor")

# Alias for readability when working with vector payloads.
Vector = List[float]


class GeminiEmbeddingClient:
    """Thin wrapper around the Google GenAI embeddings API."""

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self.model = self.config.model
        self.output_dimensionality = self.config.output_dimensionality

        effective_kwargs: MutableMapping[str, Any] = dict(self.config.client_kwargs or {})
        resolved_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")

        if resolved_key:
            effective_kwargs.setdefault("api_key", resolved_key)
        elif not effective_kwargs.get("vertexai"):
            raise ValueError(
                "Gemini API key missing. Provide api_key explicitly or set GOOGLE_API_KEY."
            )

        self._client = genai.Client(**effective_kwargs)

    def embed(self, texts: Sequence[str]) -> List[Vector]:
        """Embed a batch of texts and return their vector representations."""
        if not texts:
            return []

        trimmed_texts = [text.strip() if text else "" for text in texts]
        batch_size = max(1, self.config.batch_size)

        vectors: List[Vector] = []
        for start in range(0, len(trimmed_texts), batch_size):
            batch = trimmed_texts[start : start + batch_size]
            params: dict[str, Any] = {"model": self.model, "contents": batch}
            if self.output_dimensionality is not None:
                params["config"] = types.EmbedContentConfig(
                    output_dimensionality=self.output_dimensionality
                )

            response = self._client.models.embed_content(**params)
            embeddings = getattr(response, "embeddings", None) or []

            if len(embeddings) != len(batch):
                logger.error(
                    "Embedding batch size mismatch: expected %d, received %d",
                    len(batch),
                    len(embeddings),
                )
            for embedding in embeddings:
                values = getattr(embedding, "values", None) or []
                if not values:
                    continue
                vectors.append(list(values))

        if len(vectors) != len(trimmed_texts):
            logger.warning(
                "Embedding request returned %d vectors for %d inputs", len(vectors), len(trimmed_texts)
            )

        return vectors


__all__ = ["GeminiEmbeddingClient", "Vector"]
