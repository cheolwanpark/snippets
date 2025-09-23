"""Utilities for splitting large file payloads while keeping readable boundaries."""
from __future__ import annotations

import re
from typing import Callable, Iterable, List

_BOUNDARY_HINT = re.compile(
    r"""
    ^\s*(?:\#|//)\s*$|             # blank comment divider
    ^\s*$|                          # empty line
    ^\s*(class|interface|struct)\b| # class/struct declarations
    ^\s*(def|fn|function|async\s+def)\b|  # function style declarations
    ^\s*\w[\w:<>,\s\*\&]+\s+\w+\s*\( # C/Java style signature
    """,
    re.VERBOSE,
)


def default_boundary_score(previous_line: str, next_line: str) -> int:
    """Score how good the boundary between previous and next line is."""
    score = 0

    stripped_prev = previous_line.rstrip()
    stripped_next = next_line.lstrip()

    if not stripped_prev:
        score += 2
    if stripped_prev.endswith("}"):
        score += 3
    if stripped_prev.endswith(";"):
        score += 2
    if stripped_prev.startswith("//") or stripped_prev.startswith("#"):
        score += 1
    if _BOUNDARY_HINT.match(stripped_next):
        score += 3
    if stripped_prev.startswith("```") or stripped_next.startswith("```"):
        score += 4

    return score


def _split_large_line(line: str, max_chunk_size: int) -> Iterable[str]:
    for start in range(0, len(line), max_chunk_size):
        yield line[start : start + max_chunk_size]


def split_text(
    text: str,
    *,
    max_chunk_size: int,
    boundary_score_fn: Callable[[str, str], int] = default_boundary_score,
) -> List[str]:
    """Split text into chunks no larger than ``max_chunk_size`` characters."""
    if len(text) <= max_chunk_size:
        return [text]

    lines = text.splitlines(keepends=True)
    chunks: List[str] = []
    start = 0

    while start < len(lines):
        current_size = 0
        best_cut = None
        best_cut_size = -1
        best_score = -1

        for idx in range(start, len(lines)):
            line = lines[idx]
            line_length = len(line)

            if line_length > max_chunk_size:
                if idx > start:
                    chunk = "".join(lines[start:idx])
                    if chunk:
                        chunks.append(chunk)
                        start = idx
                        break

                chunks.extend(_split_large_line(line, max_chunk_size))
                start = idx + 1
                break

            current_size += line_length
            previous_line = line
            next_line = lines[idx + 1] if idx + 1 < len(lines) else ""

            if current_size <= max_chunk_size:
                score = boundary_score_fn(previous_line, next_line)
                if score > best_score or (score == best_score and current_size > best_cut_size):
                    best_score = score
                    best_cut = idx + 1
                    best_cut_size = current_size
                continue

            cut_index = best_cut if best_cut and best_cut > start else idx
            if cut_index == start:
                cut_index = start + 1

            chunk = "".join(lines[start:cut_index])
            if chunk:
                chunks.append(chunk)
            start = cut_index
            break
        else:
            chunk = "".join(lines[start:])
            if chunk:
                chunks.append(chunk)
            break

    # ensure chunk sizes are within limit (defensive)
    normalized: List[str] = []
    for piece in chunks:
        if len(piece) <= max_chunk_size:
            normalized.append(piece)
            continue
        normalized.extend(_split_large_line(piece, max_chunk_size))

    return normalized


def chunk_file_data(file_data: "FileData", *, max_chunk_size: int) -> List["FileData"]:
    """Return a list of FileData instances whose content respects ``max_chunk_size``."""
    if file_data.size <= max_chunk_size:
        return [file_data]

    chunks = split_text(file_data.content, max_chunk_size=max_chunk_size)

    # Import locally to avoid circular dependency during module import.
    from .file_loader import FileData

    chunked = [
        FileData(
            path=file_data.path,
            relative_path=file_data.relative_path,
            content=chunk,
            size=len(chunk),
            extension=file_data.extension,
        )
        for chunk in chunks
    ]

    return chunked
