import logging
import os

from claude_agent_sdk import (
    CLIConnectionError,
    CLINotFoundError,
    ClaudeSDKError,
    ProcessError,
)

from ..snippet import SnippetStorage
from ..wrapper import Agent
from .prompt import SYSTEM_PROMPT, PROMPT


logger = logging.getLogger("snippet_extractor")


class SnippetExtractor:
    def __init__(self) -> None:
        self.oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        if not self.oauth_token:
            raise RuntimeError("CLAUDE_CODE_OAUTH_TOKEN environment variable is required")

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
        *,
        path: str,
        content: str,
        storage: SnippetStorage,
    ) -> bool:
        """Extract snippets from pre-loaded content using provided storage. Returns True on success."""
        top_n = self._calculate_top_n(content)
        if top_n <= 0:
            logger.debug("Skipping extraction for %s due to empty content", path)
            return True

        system_prompt = SYSTEM_PROMPT.format(top_n=top_n)
        server = storage.server
        server_name = getattr(server, "name", storage.__class__.__name__.lower())
        agent = Agent(
            oauth_token=self.oauth_token,
            system_prompt=system_prompt,
            model="claude-sonnet-4-5-20250929",
            mcp_servers={server_name: server},
            allowed_tools=[],
        )

        user_prompt = PROMPT.format(
            path=path,
            top_n=top_n,
            file_content=content,
        )

        try:
            result = await agent.arun(user_prompt)
        except (CLINotFoundError, CLIConnectionError, ProcessError, ClaudeSDKError) as exc:
            logger.error("Agent.arun failed for %s: %s", path, exc)
            return False
        except Exception:
            logger.exception("Unexpected failure during Agent.arun for %s", path)
            return False

        if not isinstance(result, str):
            logger.error(
                "Agent.arun returned unsupported type for %s: %s",
                path,
                type(result).__name__,
            )
            return False

        return bool(result.strip())
