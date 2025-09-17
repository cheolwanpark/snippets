"""FastAPI application wiring for the snippets service."""

from .server import create_app

__all__ = ["create_app"]
