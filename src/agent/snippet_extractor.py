import logging
import os

from claude_agent_toolkit import (
    Agent,
    ConfigurationError,
    ConnectionError as ClaudeConnectionError,
    ExecutionError,
    ExecutorType,
)

from ..snippet import SnippetStorage
from .prompt import SYSTEM_PROMPT, PROMPT


logger = logging.getLogger("snippet_extractor")


class SnippetExtractor:
    def __init__(self) -> None:
        self.oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        self.use_subprocess = os.getenv("USE_SUBPROCESS", "false").lower() == "true"
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
        agent = Agent(
            oauth_token=self.oauth_token,
            system_prompt=system_prompt,
            tools=[storage],
            executor=ExecutorType.SUBPROCESS if self.use_subprocess else ExecutorType.DOCKER,
        )

        user_prompt = PROMPT.format(
            path=path,
            top_n=top_n,
            file_content=content,
        )

        try:
            result = await agent.run(user_prompt)
        except (ConfigurationError, ClaudeConnectionError, ExecutionError) as exc:
            logger.error("Agent.run failed for %s: %s", path, exc)
            return False
        except Exception:
            logger.exception("Unexpected failure during Agent.run for %s", path)
            return False

        if not isinstance(result, str):
            logger.error(
                "Agent.run returned unsupported type for %s: %s",
                path,
                type(result).__name__,
            )
            return False

        return bool(result.strip())
