"""Pydantic models for the public API surface."""

from __future__ import annotations

from typing import List, Sequence

from pydantic import BaseModel, Field

from ..snippet import Snippet


class RepoCreateRequest(BaseModel):
    url: str = Field(..., description="GitHub repository URL")
    branch: str | None = Field(None, description="Repository branch or ref to clone")
    include_tests: bool = Field(False, description="Include test directories when extracting")
    patterns: Sequence[str] | None = Field(
        None, description="Optional glob patterns for files to include"
    )
    max_file_size: int | None = Field(
        None,
        description="Maximum file size (bytes) to consider",
        ge=0,
    )
    repo_name: str | None = Field(
        None,
        description="Optional repository identifier to store alongside snippets",
    )


class RepoSummary(BaseModel):
    id: str
    url: str
    repo_name: str | None = None
    status: str
    process_message: str | None = None
    fail_reason: str | None = None
    progress: int | None = None


class RepoDetailResponse(RepoSummary):
    created_at: str | None = None
    updated_at: str | None = None
    snippet_count: int | None = None


class RepoCreateResponse(RepoSummary):
    pass


class SnippetResponse(BaseModel):
    title: str
    description: str
    language: str
    code: str
    path: str
    repo_name: str | None = None
    repo_url: str | None = None

    @classmethod
    def from_snippet(cls, snippet: Snippet) -> "SnippetResponse":
        return cls(
            title=snippet.title,
            description=snippet.description,
            language=snippet.language,
            code=snippet.code,
            path=snippet.path,
            repo_name=getattr(snippet, "repo_name", None) or snippet.repo,
            repo_url=getattr(snippet, "repo_url", None),
        )


class SnippetQueryResponse(BaseModel):
    query: str
    results: List[SnippetResponse]


__all__ = [
    "RepoCreateRequest",
    "RepoSummary",
    "RepoDetailResponse",
    "RepoCreateResponse",
    "SnippetResponse",
    "SnippetQueryResponse",
]
