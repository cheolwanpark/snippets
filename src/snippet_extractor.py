import os
from claude_agent_toolkit import Agent, ConfigurationError
from .snippet_storage import SnippetStorage
from .prompt import SYSTEM_PROMPT, PROMPT


class SnippetExtractor:
    def __init__(self):
        self.oauth_token = os.getenv('CLAUDE_CODE_OAUTH_TOKEN')
        if not self.oauth_token:
            raise ConfigurationError("CLAUDE_CODE_OAUTH_TOKEN environment variable is required")
    
    async def extract_from_content(self, filename: str, content: str, 
                                   storage: SnippetStorage, top_n: int = 10) -> bool:
        """Extract snippets from pre-loaded content using provided storage. Returns True on success."""
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
        return result.get("success", False)
    
