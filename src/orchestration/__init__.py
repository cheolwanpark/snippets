"""Orchestration components for coordinating snippet extraction."""

from .extraction import ExtractionPipeline, extract_snippets_from_path

__all__ = ["ExtractionPipeline", "extract_snippets_from_path"]
