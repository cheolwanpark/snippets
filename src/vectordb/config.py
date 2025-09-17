from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping


@dataclass(slots=True)
class DBConfig:
    """Connection information for Qdrant."""

    url: str | None = None
    api_key: str | None = None
    collection_name: str = "snippet_embeddings"
    upsert_batch_size: int = 100

    def client_kwargs(self) -> dict[str, str]:
        kwargs: dict[str, str] = {}
        if self.url:
            kwargs["url"] = self.url
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return kwargs


@dataclass(slots=True)
class EmbeddingConfig:
    """Configuration for Gemini embeddings."""

    api_key: str | None = None
    model: str = "text-embedding-004"
    output_dimensionality: int | None = None
    client_kwargs: MutableMapping[str, Any] | None = None
    batch_size: int = 100


__all__ = ["DBConfig", "EmbeddingConfig"]
