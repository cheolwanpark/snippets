"""FastAPI application factory for the snippets service."""

from __future__ import annotations

from fastapi import FastAPI

from .routes import ApiSettings, router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = ApiSettings.from_env()
    app = FastAPI(title="Snippet Repository API", version="0.1.0")
    app.state.settings = settings
    app.include_router(router)
    return app


app = create_app()


__all__ = ["app", "create_app"]
