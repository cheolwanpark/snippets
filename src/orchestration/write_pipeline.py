from __future__ import annotations

import logging
from typing import Optional, Sequence

from .extraction import ExtractionPipeline
from ..vectordb.config import DBConfig, EmbeddingConfig
from ..vectordb.writer import SnippetVectorWriter

logger = logging.getLogger("snippet_extractor")


def write_snippets_to_vectordb(
    directory: str,
    db_config: DBConfig,
    embedding_config: EmbeddingConfig,
    *,
    top_n: int = 10,
    max_file_size: Optional[int] = None,
    include_tests: bool = False,
    extensions: Optional[Sequence[str]] = None,
    concurrency: int = 5,
) -> None:
    """Extract snippets from a directory and upload them to the vector DB."""
    if not directory:
        raise ValueError("directory is required")
    if db_config is None:
        raise ValueError("db_config is required")

    pipeline = ExtractionPipeline(
        max_concurrency=concurrency,
        extensions=extensions,
        max_file_size=max_file_size,
        include_tests=include_tests,
    )

    snippets = pipeline.run(directory, top_n=top_n)
    if not snippets:
        logger.info("No snippets extracted from %s; skipping upload", directory)
        return

    writer = SnippetVectorWriter(db_config, embedding_config)

    written = writer.write(snippets)
    logger.info(
        "Uploaded %d snippets to Qdrant collection %s",
        written,
        db_config.collection_name,
    )

    if pipeline.errors:
        logger.warning("Extraction completed with %d errors", len(pipeline.errors))


__all__ = ["write_snippets_to_vectordb"]
