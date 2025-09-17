from __future__ import annotations

from typing import Any, Annotated, Dict, List

from claude_agent_toolkit import BaseTool, tool

from .model import Snippet


class SnippetStorage(BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.state: Dict[str, Dict[str, List[Snippet]]] = {"snippets": {}}

    def register_file(self, path: str) -> None:
        """Ensure storage tracks the given path even if no snippets are added."""
        snippets_by_path: Dict[str, List[Snippet]] = self.state["snippets"]
        if path not in snippets_by_path:
            snippets_by_path[path] = []

    @tool(description="Store an extracted code snippet for later processing")
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
        """Add a code snippet to the storage with lightweight validation."""
        if not title or not description or not language or not code or not path:
            return {
                "added": False,
                "error": "All fields (title, description, language, code, path) are required",
            }

        self.register_file(path)

        snippet = Snippet(
            title=title,
            description=description,
            language=language,
            code=code,
            path=path,
        )

        self.state["snippets"][path].append(snippet)

        total_count = self.get_snippet_count()

        return {
            "added": True,
            "path": path,
            "file_count": len(self.state["snippets"][path]),
            "total_count": total_count,
            "title": snippet.title,
        }

    def to_file(self) -> str:
        """Convert accumulated snippets from all files into formatted output string."""
        snippets_by_path: Dict[str, List[Snippet]] = self.state["snippets"]
        if not snippets_by_path:
            return (
                "-----\n\n"
                "TITLE: No Qualifying Snippets Found\n"
                "DESCRIPTION: No source files contain library/API usage patterns or "
                "best-practice implementations that meet the extraction criteria.\n"
                "SOURCE: N/A\n"
                "LANGUAGE: Unknown\n"
                "CODE:\n\n"
                "# No qualifying snippets found in any source files.\n"
            )

        output_parts: List[str] = []

        for path, snippets in snippets_by_path.items():
            if not snippets:
                output_parts.extend(
                    [
                        "-----\n\n",
                        "TITLE: No Qualifying Snippets Found\n",
                        (
                            f"DESCRIPTION: The file ({path}) does not contain any "
                            "library/API usage patterns or best-practice implementations that meet "
                            "the extraction criteria.\n"
                        ),
                        f"SOURCE: {path}\n",
                        "LANGUAGE: Unknown\n",
                        "CODE:\n\n",
                        "# No qualifying snippets found in this file.\n\n",
                    ]
                )
                continue

            for snippet in snippets:
                output_parts.extend(
                    [
                        "-----\n\n",
                        f"TITLE: {snippet.title}\n",
                        f"DESCRIPTION: {snippet.description}\n",
                        f"SOURCE: {snippet.path}\n",
                        f"LANGUAGE: {snippet.language}\n",
                        "CODE:\n",
                        f"```\n{snippet.code}\n```\n\n",
                    ]
                )

        return "".join(output_parts)

    def get_snippet_count(self) -> int:
        """Get the total number of stored snippets across all files."""
        return sum(len(snippets) for snippets in self.state["snippets"].values())

    def get_files_processed(self) -> int:
        """Get the number of files that have been processed."""
        return len(self.state["snippets"])

    def get_all_snippets(self) -> List[Snippet]:
        """Return all stored snippets as a flat list."""
        snippets_by_path = self.state["snippets"]
        return [snippet for snippets in snippets_by_path.values() for snippet in snippets]

    def clear_snippets(self) -> None:
        """Clear all stored snippets."""
        self.state["snippets"] = {}
