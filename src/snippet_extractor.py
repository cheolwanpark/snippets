import os
from claude_adk import Agent
from .snippet_storage import SnippetStorage
from .prompt import SYSTEM_PROMPT, PROMPT


class SnippetExtractor:
    def __init__(self):
        self.oauth_token = os.getenv('CLAUDE_CODE_OAUTH_TOKEN')
        if not self.oauth_token:
            raise ValueError("CLAUDE_CODE_OAUTH_TOKEN environment variable is required")
    
    async def extract_from_content(self, filename: str, content: str, 
                                   top_n: int = 10, storage=None) -> dict:
        """Extract snippets from pre-loaded content - no file I/O."""
        try:
            # Use provided storage or create own
            own_storage = False
            if storage is None:
                storage = SnippetStorage()
                storage.run(workers=1)
                own_storage = True
            
            # Create agent
            system_prompt = SYSTEM_PROMPT.format(top_n=top_n)
            agent = Agent(
                oauth_token=self.oauth_token,
                system_prompt=system_prompt,
                tools=[storage]
            )
            
            # Format prompt with pre-loaded content
            user_prompt = PROMPT.format(
                filename=filename,
                top_n=top_n,
                file_content=content
            )
            
            # Run agent
            result = await agent.run(user_prompt)
            
            if own_storage and result["success"]:
                result["response"] = storage.to_file()
                result["snippets_extracted"] = storage.get_snippet_count()
                
            return result
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error processing {filename}: {str(e)}",
                "error": type(e).__name__
            }
    
