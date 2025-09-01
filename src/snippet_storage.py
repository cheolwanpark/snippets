from claude_adk import BaseTool, tool
from typing import Dict, Any


class SnippetStorage(BaseTool):
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename  # Non-state property
        self.state = {"snippets": []}  # State: list of snippets
    
    @tool(description="Add extracted code snippet with structured format")
    async def add_snippet(self, title: str, description: str, language: str, code: str) -> Dict[str, Any]:
        """Add a code snippet to the storage with validation."""
        # Validate required fields
        if not title or not description or not language or not code:
            return {
                "added": False, 
                "error": "All fields (title, description, language, code) are required"
            }
        
        # Create structured snippet
        snippet = {
            "title": title.strip(),
            "description": description.strip(),
            "language": language.strip(),
            "code": code.strip()
        }
        
        # Store in state
        self.state["snippets"].append(snippet)
        
        return {
            "added": True, 
            "count": len(self.state["snippets"]),
            "title": title
        }
    
    def to_file(self) -> str:
        """Convert accumulated snippets into formatted output string."""
        if not self.state["snippets"]:
            return (
                "-----\n\n"
                "TITLE: No Qualifying Snippets Found\n"
                f"DESCRIPTION: The provided file ({self.filename}) does not contain any "
                "library/API usage patterns or best-practice implementations that meet "
                "the extraction criteria.\n"
                f"SOURCE: {self.filename}\n"
                "LANGUAGE: Unknown\n"
                "CODE:\n\n"
                "# No qualifying snippets found in the source file.\n"
            )
        
        output_parts = []
        
        for snippet in self.state["snippets"]:
            output_parts.extend([
                "-----\n\n",
                f"TITLE: {snippet['title']}\n",
                f"DESCRIPTION: {snippet['description']}\n",
                f"SOURCE: {self.filename}\n",
                f"LANGUAGE: {snippet['language']}\n",
                "CODE:\n",
                f"{snippet['code']}\n\n"
            ])
        
        return "".join(output_parts)
    
    def get_snippet_count(self) -> int:
        """Get the current number of stored snippets."""
        return len(self.state["snippets"])
    
    def clear_snippets(self) -> None:
        """Clear all stored snippets."""
        self.state["snippets"] = []