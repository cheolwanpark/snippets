from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Snippet(BaseModel):
    """Structured representation of an extracted snippet ready for storage."""

    title: str
    description: str
    language: str
    code: str
    path: str
    repo: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


__all__ = ["Snippet"]
