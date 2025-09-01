import asyncio
import os
from claude_adk import Agent
from .snippet_storage import SnippetStorage
from .prompt import SYSTEM_PROMPT, PROMPT


class SnippetExtractor:
    def __init__(self):
        self.oauth_token = os.getenv('CLAUDE_CODE_OAUTH_TOKEN')
        if not self.oauth_token:
            raise ValueError("CLAUDE_CODE_OAUTH_TOKEN environment variable is required")
    
    async def extract_snippets(self, file_path: str, top_n: int = 10) -> dict:
        """Extract code snippets from a single file using SnippetStorage Tool."""
        storage = None
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # Get filename
            filename = os.path.basename(file_path)
            
            # Create and start SnippetStorage tool
            storage = SnippetStorage(filename=filename)
            storage.run(workers=1)  # Start tool server
            
            # Create agent with tool-aware system prompt
            system_prompt = SYSTEM_PROMPT.format(top_n=top_n)
            agent = Agent(
                oauth_token=self.oauth_token,
                system_prompt=system_prompt,
                tools=[storage]  # Connect tool at initialization
            )
            
            # Format prompt with file content
            user_prompt = PROMPT.format(
                filename=filename,
                top_n=top_n,
                file_content=file_content
            )
            
            # Run agent
            result = await agent.run(user_prompt)
            
            if result["success"]:
                # Get formatted output from tool
                formatted_output = storage.to_file()
                return {
                    "success": True,
                    "response": formatted_output,
                    "execution_time": result.get("execution_time"),
                    "tools_used": result.get("tools_used", []),
                    "snippets_extracted": storage.get_snippet_count()
                }
            else:
                return result
            
        except FileNotFoundError:
            return {
                "success": False,
                "response": f"File not found: {file_path}",
                "error": "FileNotFoundError"
            }
        except Exception as e:
            return {
                "success": False,
                "response": f"Error processing file: {str(e)}",
                "error": type(e).__name__
            }
        finally:
            # Ensure tool is properly shut down
            if storage:
                try:
                    # Tool cleanup handled by claude-adk framework
                    pass
                except:
                    pass  # Ignore shutdown errors


def extract_snippets_sync(file_path: str, top_n: int = 10) -> dict:
    """Synchronous wrapper for snippet extraction."""
    extractor = SnippetExtractor()
    return asyncio.run(extractor.extract_snippets(file_path, top_n))