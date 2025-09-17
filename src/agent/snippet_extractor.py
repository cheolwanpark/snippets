import logging
import os

from claude_agent_toolkit import (
    Agent,
    ConfigurationError,
    ConnectionError as ClaudeConnectionError,
    ExecutionError,
)
from ..snippet.snippet_storage import SnippetStorage
from .prompt import SYSTEM_PROMPT, PROMPT


logger = logging.getLogger("snippet_extractor")


class SnippetExtractor:
    def __init__(self):
        self.oauth_token = os.getenv('CLAUDE_CODE_OAUTH_TOKEN')
        if not self.oauth_token:
            raise ConfigurationError("CLAUDE_CODE_OAUTH_TOKEN environment variable is required")

    def _calculate_top_n(self, content: str) -> int:
        """Return the max snippets to extract based on line count heuristic."""
        if not content:
            return 0

        line_count = content.count("\n")
        if content and not content.endswith("\n"):
            line_count += 1

        if line_count == 0:
            return 0

        top_n = line_count // 20
        return max(1, top_n)

    async def extract_from_content(
        self,
        filename: str,
        content: str,
        storage: SnippetStorage,
    ) -> bool:
        """Extract snippets from pre-loaded content using provided storage. Returns True on success."""
        top_n = self._calculate_top_n(content)
        if top_n <= 0:
            logger.debug("Skipping extraction for %s due to empty content", filename)
            return True

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
        try:
            result = await agent.run(user_prompt)
        except (ConfigurationError, ClaudeConnectionError, ExecutionError) as exc:
            logger.error("Agent.run failed for %s: %s", filename, exc)
            return False
        except Exception:
            logger.exception("Unexpected failure during Agent.run for %s", filename)
            return False

        if not isinstance(result, str):
            logger.error(
                "Agent.run returned unsupported type for %s: %s",
                filename,
                type(result).__name__,
            )
            return False

        return bool(result.strip())
