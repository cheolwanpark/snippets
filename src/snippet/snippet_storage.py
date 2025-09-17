from __future__ import annotations

from typing import Any, Dict, List

from claude_agent_toolkit import BaseTool, tool
from pydantic import BaseModel, field_validator


class Snippet(BaseModel):
    """Structured representation of an extracted snippet."""

    title: str
    description: str
    language: str
    code: str
    filename: str

    @field_validator("title", "description", "language", "code", "filename", mode="before")
    @classmethod
    def _strip_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


class SnippetStorage(BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.state: Dict[str, Dict[str, List[Snippet]]] = {"snippets": {}}

    def register_file(self, filename: str) -> None:
        """Ensure storage tracks the given filename even if no snippets are added."""
        snippets_by_file: Dict[str, List[Snippet]] = self.state["snippets"]
        if filename not in snippets_by_file:
            snippets_by_file[filename] = []

    @tool(description="Add extracted code snippet with structured format")
    async def add_snippet(
        self,
        title: str,
        description: str,
        language: str,
        code: str,
        filename: str,
    ) -> Dict[str, Any]:
        """Add a code snippet to the storage with validation."""
        if not title or not description or not language or not code or not filename:
            return {
                "added": False,
                "error": "All fields (title, description, language, code, filename) are required",
            }

        self.register_file(filename)

        snippet = Snippet(
            title=title,
            description=description,
            language=language,
            code=code,
            filename=filename,
        )

        self.state["snippets"][filename].append(snippet)

        total_count = self.get_snippet_count()

        return {
            "added": True,
            "file": filename,
            "file_count": len(self.state["snippets"][filename]),
            "total_count": total_count,
            "title": snippet.title,
        }

    def to_file(self) -> str:
        """Convert accumulated snippets from all files into formatted output string."""
        snippets_by_file: Dict[str, List[Snippet]] = self.state["snippets"]
        if not snippets_by_file:
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

        for filename, snippets in snippets_by_file.items():
            if not snippets:
                output_parts.extend(
                    [
                        "-----\n\n",
                        "TITLE: No Qualifying Snippets Found\n",
                        (
                            f"DESCRIPTION: The file ({filename}) does not contain any "
                            "library/API usage patterns or best-practice implementations that meet "
                            "the extraction criteria.\n"
                        ),
                        f"SOURCE: {filename}\n",
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
                        f"SOURCE: {snippet.filename}\n",
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
        snippets_by_file = self.state["snippets"]
        return [snippet for snippets in snippets_by_file.values() for snippet in snippets]

    def clear_snippets(self) -> None:
        """Clear all stored snippets."""
        self.state["snippets"] = {}
