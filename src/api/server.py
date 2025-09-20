"""FastAPI application factory for the snippets service."""

from __future__ import annotations

from fastapi import FastAPI

from .route import router
from .service import ApiSettings
from ..mcpserver import mcp


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    # setup mcp
    mcp_app = mcp.http_app("/")

    settings = ApiSettings.from_env()
    app = FastAPI(
        title="Snippet Repository API", 
        version="0.1.0",
        lifespan=mcp_app.lifespan,
    )
    app.state.settings = settings
    app.include_router(router)

    # mount mcp
    app.mount("/mcp", mcp_app)


    return app


app = create_app()


__all__ = ["app", "create_app"]
