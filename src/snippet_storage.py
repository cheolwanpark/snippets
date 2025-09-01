from claude_adk import BaseTool, tool
from typing import Dict, Any


class SnippetStorage(BaseTool):
    def __init__(self):
        super().__init__()
        self.state = {"snippets": {}}  # State: dict keyed by filename
    
    @tool(description="Add extracted code snippet with structured format")
    async def add_snippet(self, title: str, description: str, language: str, code: str, filename: str) -> Dict[str, Any]:
        """Add a code snippet to the storage with validation."""
        # Validate required fields
        if not title or not description or not language or not code or not filename:
            return {
                "added": False, 
                "error": "All fields (title, description, language, code, filename) are required"
            }
        
        # Initialize filename entry if needed
        if filename not in self.state["snippets"]:
            self.state["snippets"][filename] = []
        
        # Create structured snippet
        snippet = {
            "title": title.strip(),
            "description": description.strip(),
            "language": language.strip(),
            "code": code.strip()
        }
        
        # Store in state under filename
        self.state["snippets"][filename].append(snippet)
        
        # Calculate total snippet count
        total_count = sum(len(snippets) for snippets in self.state["snippets"].values())
        
        return {
            "added": True, 
            "file": filename,
            "file_count": len(self.state["snippets"][filename]),
            "total_count": total_count,
            "title": title
        }
    
    def to_file(self) -> str:
        """Convert accumulated snippets from all files into formatted output string."""
        if not self.state["snippets"]:
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
        
        output_parts = []
        
        # Process all files and their snippets
        for filename, snippets in self.state["snippets"].items():
            if not snippets:
                # Handle empty file
                output_parts.extend([
                    "-----\n\n",
                    "TITLE: No Qualifying Snippets Found\n",
                    f"DESCRIPTION: The file ({filename}) does not contain any "
                    "library/API usage patterns or best-practice implementations that meet "
                    "the extraction criteria.\n",
                    f"SOURCE: {filename}\n",
                    "LANGUAGE: Unknown\n",
                    "CODE:\n\n",
                    "# No qualifying snippets found in this file.\n\n"
                ])
            else:
                # Handle file with snippets
                for snippet in snippets:
                    output_parts.extend([
                        "-----\n\n",
                        f"TITLE: {snippet['title']}\n",
                        f"DESCRIPTION: {snippet['description']}\n",
                        f"SOURCE: {filename}\n",
                        f"LANGUAGE: {snippet['language']}\n",
                        "CODE:\n",
                        f"```\n{snippet['code']}\n```\n\n"
                    ])
        
        return "".join(output_parts)
    
    def get_snippet_count(self) -> int:
        """Get the total number of stored snippets across all files."""
        return sum(len(snippets) for snippets in self.state["snippets"].values())
    
    def get_files_processed(self) -> int:
        """Get the number of files that have been processed."""
        return len(self.state["snippets"])
    
    def clear_snippets(self) -> None:
        """Clear all stored snippets."""
        self.state["snippets"] = {}