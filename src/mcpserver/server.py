"""FastMCP server exposing snippet repository helpers as MCP tools."""

from __future__ import annotations

import logging
from typing import Any, Dict
from fastapi import HTTPException
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..api.service import (
    ApiSettings,
    query_snippets_service,
)
from ..vectordb.config import DBConfig, EmbeddingConfig
from ..vectordb.reader import SnippetVectorReader
logger = logging.getLogger("snippet_extractor")


class ServiceContext:
    """Lazy dependency container for MCP tool handlers."""

    def __init__(self) -> None:
        self._settings: ApiSettings | None = None
        self._reader: SnippetVectorReader | None = None

    @property
    def settings(self) -> ApiSettings:
        if self._settings is None:
            self._settings = ApiSettings.from_env()
        return self._settings

    def reader(self) -> SnippetVectorReader:
        if self._reader is None:
            db_config = DBConfig(
                url=self.settings.qdrant_url,
                api_key=self.settings.qdrant_api_key,
                collection_name=self.settings.qdrant_collection,
            )
            embedding_config = EmbeddingConfig(
                api_key=self.settings.embedding_api_key,
                model=self.settings.embedding_model,
                output_dimensionality=self.settings.embedding_output_dim,
                batch_size=self.settings.embedding_batch_size,
            )
            self._reader = SnippetVectorReader(db_config, embedding_config)
        return self._reader


def _handle_http_exception(exc: HTTPException, *, default_message: str) -> ToolError:
    detail = exc.detail if isinstance(exc.detail, str) else None
    message = detail or default_message
    return ToolError(message)


def _handle_generic_exception(exc: Exception, *, default_message: str) -> ToolError:
    logger.exception(default_message)
    return ToolError(f"{default_message}: {exc}")


def create_server() -> FastMCP:
    """Create a FastMCP server wired to snippet repository services."""

    services = ServiceContext()
    server = FastMCP("Snippets MCP Server")

    @server.tool(
        name="search",
        description=(
            "Search stored snippets using semantic similarity. Start with just your query with high limit;"
            " `limit` defaults to 10 and can be bumped to 20-50 if you're unsure (try 50 when"
            " exploring). Use optional `repo_name` and `language` filters for follow-up searches"
            " once you learn which repository or language to target."
        ),
        tags={"snippets", "search"},
    )
    def search(
        query: str,
        limit: int = 10,
        repo_name: str | None = None,
        language: str | None = None,
    ) -> Dict[str, Any]:
        """Query stored snippets and return structured search results."""
        if not query or not query.strip():
            raise ToolError("Query text is required.")

        normalized_limit = limit or 10
        if normalized_limit <= 0:
            raise ToolError("Limit must be a positive integer.")
        if normalized_limit > 50:
            normalized_limit = 50

        language_filter = language.lower() if language else None

        try:
            response = query_snippets_service(
                query=query,
                limit=normalized_limit,
                reader=services.reader(),
                repo_name=repo_name,
                language=language_filter,
            )
        except HTTPException as exc:  # pragma: no cover - defensive
            raise _handle_http_exception(exc, default_message="Snippet search failed")
        except Exception as exc:  # pragma: no cover - defensive
            raise _handle_generic_exception(exc, default_message="Snippet search failed")

        return response.model_dump()

    return server


mcp = create_server()

__all__ = ["mcp"]
