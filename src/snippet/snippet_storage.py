from __future__ import annotations

from typing import Any, Annotated, Dict, List

from ..wrapper import BaseTool, tool

from .model import Snippet


class SnippetStorage(BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.snippets = []

    @tool()
    async def add_snippet(
        self,
        *,
        title: Annotated[str, "Descriptive title under 80 characters"],
        description: Annotated[
            str,
            "2-4 sentence explanation of what the snippet does and why it matters",
        ],
        language: Annotated[str, "Programming language name (for example, 'Python')"],
        code: Annotated[str, "Verbatim code snippet to persist"],
        path: Annotated[str, "Repository-relative path of the source file"],
    ) -> Dict[str, Any]:
        """Store an extracted code snippet for later processing."""
        if not title or not description or not language or not code or not path:
            return {
                "added": False,
                "error": "All fields (title, description, language, code, path) are required",
            }

        snippet = Snippet(
            title=title,
            description=description,
            language=language,
            code=code,
            path=path,
        )

        self.snippets.append(snippet)

        total_count = self.get_snippet_count()

        return {
            "added": True,
            "path": path,
            "total_count": total_count,
            "title": snippet.title,
        }

    def get_snippet_count(self) -> int:
        """Get the total number of stored snippets across all files."""
        return len(self.snippets)

    def get_all_snippets(self) -> List[Snippet]:
        """Return all stored snippets as a flat list."""
        return self.snippets

    def clear_snippets(self) -> None:
        """Clear all stored snippets."""
        self.snippets = []
