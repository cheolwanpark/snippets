"""Wrapper for the Claude Agent SDK."""
from __future__ import annotations

import inspect
import json
import sys
import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import count
from typing import (
    Any, Awaitable, Callable, 
    Dict, List, Optional, 
    Tuple, Union, get_args, 
    get_origin, get_type_hints,
    MutableMapping
)
from pathlib import Path

try:  # Python <3.10 compatibility
    from types import UnionType as _UnionType  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - older Python versions
    _UnionType = None  # type: ignore[assignment]

from claude_agent_sdk import (
    McpSdkServerConfig,
    SdkMcpTool,
    create_sdk_mcp_server,
    AssistantMessage,
    ClaudeAgentOptions,
    ContentBlock,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.lowlevel.server import Server as McpServer
import mcp.types as types

ToolArguments = Dict[str, Any]
ToolResult = Dict[str, Any]
AsyncToolHandler = Callable[[ToolArguments], Awaitable[ToolResult]]

Pathish = Union[str, Path]
MCPConfig = Mapping[str, Any]

_counter = count()


def _safe_signature(target: Any) -> inspect.Signature | None:
    try:
        return inspect.signature(target)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


_options_signature = _safe_signature(ClaudeAgentOptions)
_option_parameter_names: set[str] = (
    set(_options_signature.parameters) if _options_signature else set()
)


def _option_supported(name: str) -> bool:
    return name in _option_parameter_names


def _get_mcp_field(mcp_config: Any, field: str, default: Any = None) -> Any:
    """Best-effort attribute lookup supporting dataclasses, dicts, and Pydantic models."""
    if isinstance(mcp_config, Mapping):
        return mcp_config.get(field, default)

    if hasattr(mcp_config, field):
        return getattr(mcp_config, field)

    if hasattr(mcp_config, "__dict__") and field in mcp_config.__dict__:
        return mcp_config.__dict__[field]

    for exporter_name in ("model_dump", "dict"):
        exporter = getattr(mcp_config, exporter_name, None)
        if callable(exporter):
            try:
                exported = exporter()
            except TypeError:
                continue
            if isinstance(exported, Mapping) and field in exported:
                return exported[field]

    return default


@dataclass(slots=True)
class _ToolConfig:
    """Metadata captured by the :func:`tool` decorator."""

    explicit_name: str | None
    explicit_description: str | None
    explicit_schema: dict[str, Any] | None
    order: int


@dataclass(slots=True)
class _RegisteredTool:
    """Internal representation of a registered tool."""

    name: str
    description: str
    schema: dict[str, Any]
    handler: AsyncToolHandler


def tool(
    name: str | Callable[..., Any] | None = None,
    *,
    description: str | None = None,
    schema: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that marks a method as an MCP tool.

    Parameters are optional; when omitted the method name and docstring are used
    to populate the tool metadata. ``schema`` can be provided to override the
    inferred argument schema.
    """

    def _decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        config = _ToolConfig(
            explicit_name=name if isinstance(name, str) else None,
            explicit_description=description,
            explicit_schema=schema,
            order=next(_counter),
        )
        setattr(func, "__tool_config__", config)
        return func

    if callable(name) and not isinstance(name, str):
        func = name
        name = None  # type: ignore[assignment]
        return _decorate(func)

    return _decorate


class BaseTool:
    """Base class for defining in-process MCP tool collections.

    Subclasses decorated their async methods with :func:`tool`. Instantiating
    the subclass automatically discovers the decorated methods and registers
    them as SDK MCP tools.
    """

    tool_server_name: str | None = None
    tool_server_version: str = "1.0.0"

    def __init__(self) -> None:
        self._resolved_server_name = (
            self.tool_server_name or self.__class__.__name__.lower()
        )
        self._registered_tools: List[_RegisteredTool] = self._discover_tools()
        self._sdk_tools: Optional[List[SdkMcpTool[Any]]] = None
        self._server: Optional[McpSdkServerConfig] = None

    @property
    def server(self) -> McpSdkServerConfig:
        """Lazily create and return the MCP server configuration."""
        if self._server is None:
            sdk_tools = self._build_sdk_tools()
            self._server = create_sdk_mcp_server(
                name=self._resolved_server_name,
                version=self.tool_server_version,
                tools=sdk_tools,
            )
        return self._server

    def _build_sdk_tools(self) -> List[SdkMcpTool[Any]]:
        if self._sdk_tools is None:
            self._sdk_tools = [
                SdkMcpTool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.schema,
                    handler=tool.handler,
                )
                for tool in self._registered_tools
            ]
        return self._sdk_tools

    def _discover_tools(self) -> List[_RegisteredTool]:
        discovered: Dict[str, Tuple[int, Callable[..., Any], _ToolConfig]] = {}
        for cls in self.__class__.mro():
            for attr_name, attr_value in cls.__dict__.items():
                config = getattr(attr_value, "__tool_config__", None)
                if config is None:
                    continue
                if attr_name in discovered:
                    continue
                discovered[attr_name] = (config.order, attr_value, config)

        ordered_entries = sorted(discovered.values(), key=lambda entry: entry[0])
        registry: List[_RegisteredTool] = []

        for _, func, config in ordered_entries:
            bound_method = getattr(self, func.__name__)
            if not inspect.iscoroutinefunction(bound_method):
                raise TypeError(
                    f"Tool '{func.__name__}' must be defined as an async function"
                )

            name = config.explicit_name or func.__name__
            description = (
                config.explicit_description
                or inspect.getdoc(func)
                or ""
            )
            if config.explicit_schema is not None:
                schema = dict(config.explicit_schema)
            else:
                schema = self._infer_schema(func)

            async def handler(
                arguments: ToolArguments,
                _method: Callable[..., Awaitable[ToolResult]] = bound_method,
                _tool_name: str = name,
            ) -> ToolResult:
                if not isinstance(arguments, dict):
                    raise TypeError(
                        f"Tool '{_tool_name}' expected dict arguments but received {type(arguments)!r}"
                    )
                try:
                    result = await _method(**arguments)
                except Exception as exc:  # pragma: no cover - log and surface via MCP error payload
                    return self._wrap_tool_error(exc)

                return self._wrap_tool_result(result)

            registry.append(_RegisteredTool(name, description, schema, handler))

        return registry

    def _infer_schema(self, func: Callable[..., Any]) -> dict[str, Any]:
        signature = inspect.signature(func)
        try:
            annotations = get_type_hints(func)
        except Exception:
            annotations = dict(getattr(func, "__annotations__", {}))

        schema: dict[str, Any] = {}
        for param in signature.parameters.values():
            if param.name == "self":
                continue
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                raise TypeError(
                    f"Tool '{func.__name__}' cannot use *args or **kwargs"
                )
            annotation = annotations.get(param.name, param.annotation)
            resolved = self._resolve_annotation(annotation)
            schema[param.name] = resolved

        return schema

    def _resolve_annotation(self, annotation: Any) -> Any:
        if annotation is inspect.Signature.empty:
            return str
        if annotation is Any:
            return str
        if isinstance(annotation, type):
            return annotation

        origin = get_origin(annotation)
        if origin is None:
            return str

        is_union = origin is Union or (
            _UnionType is not None and origin is _UnionType
        )
        if is_union:
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if len(args) == 1:
                return self._resolve_annotation(args[0])
            return str

        if str(origin) == "typing.Union":  # Fallback for older typing behavior
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if len(args) == 1:
                return self._resolve_annotation(args[0])
            return str

        # Default fallback for unsupported complex annotations
        return str

    @property
    def registry(self) -> List[dict[str, Any]]:
        """Return a shallow copy of registered tool metadata."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": dict(tool.schema),
            }
            for tool in self._registered_tools
        ]

    def _wrap_tool_result(self, result: Any) -> ToolResult:
        """Normalize tool handler return values into MCP-compatible payloads."""
        if isinstance(result, dict) and "content" in result:
            return result

        if isinstance(result, Mapping):
            payload = {"type": "json", "data": dict(result)}
        elif isinstance(result, (list, tuple, set)):
            payload = {"type": "json", "data": {"items": list(result)}}
        elif isinstance(result, Sequence) and not isinstance(result, (str, bytes, bytearray)):
            payload = {"type": "json", "data": {"items": list(result)}}
        else:
            text: str
            if isinstance(result, str):
                text = result
            elif isinstance(result, bytes):
                text = result.decode("utf-8", errors="replace")
            elif result is None:
                text = ""
            else:
                text = str(result)
            payload = {"type": "text", "text": text}

        return {"content": [payload]}

    def _wrap_tool_error(self, error: Exception) -> ToolResult:
        """Convert exceptions into MCP error payloads."""
        return {
            "content": [
                {
                    "type": "error",
                    "error": str(error) or error.__class__.__name__,
                }
            ],
            "is_error": True,
        }


class Agent:
    """Thin wrapper that prepares ``ClaudeAgentOptions`` and runs prompts."""

    def __init__(
        self,
        *,
        cwd: Optional[Pathish] = None,
        mcp_servers: Optional[MCPConfig] = None,
        allowed_tools: Optional[Sequence[str]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        oauth_token: Optional[str] = None,
    ) -> None:
        option_kwargs: MutableMapping[str, Any] = {}

        if cwd is not None and _option_supported("cwd"):
            option_kwargs["cwd"] = Path(cwd)

        if mcp_servers is not None and _option_supported("mcp_servers"):
            option_kwargs["mcp_servers"] = dict(mcp_servers)

        allowed_tools_list = list(allowed_tools) if allowed_tools is not None else []
        if _option_supported("allowed_tools"):
            option_kwargs["allowed_tools"] = allowed_tools_list

        if system_prompt is not None and _option_supported("system_prompt"):
            option_kwargs["system_prompt"] = system_prompt

        if model is not None and _option_supported("model"):
            option_kwargs["model"] = model

        if oauth_token is not None and _option_supported("oauth_token"):
            option_kwargs["oauth_token"] = oauth_token

        self._options = ClaudeAgentOptions(**option_kwargs)

    async def arun(self, prompt: str, *, verbose: bool = False) -> Optional[str]:
        """Asynchronously run ``prompt`` and return aggregated assistant text."""
        if not prompt:
            raise ValueError("prompt must be a non-empty string")

        result: Optional[str] = None

        # Claude Agent SDK requires streaming mode to initialize SDK MCP servers.
        use_streaming = bool(getattr(self._options, "mcp_servers", None))
        self._options = await self._extend_allowed_tools(self._options)

        if use_streaming:
            from claude_agent_sdk import ClaudeSDKClient

            client = ClaudeSDKClient(options=self._options)
            await client.connect()
            try:
                await client.query(prompt)
                async for message in client.receive_response():
                    if verbose:
                        formatted = self._format_message(message)
                        if formatted:
                            _print_verbose_message(formatted)
                    if isinstance(message, ResultMessage):
                        result = message.result
            finally:
                await client.disconnect()
        else:
            async for message in query(prompt=prompt, options=self._options):
                if verbose:
                    formatted = self._format_message(message)
                    if formatted:
                        _print_verbose_message(formatted)

                if isinstance(message, ResultMessage):
                    result = message.result

        return result

    def run(self, prompt: str, *, verbose: bool = False) -> Optional[str]:
        """Synchronously run ``prompt``; see :meth:`arun` for semantics."""
        return asyncio.run(self.arun(prompt, verbose=verbose))

    async def _extend_allowed_tools(self, options: ClaudeAgentOptions) -> ClaudeAgentOptions:
        mcp_servers = getattr(options, "mcp_servers", None)
        if not mcp_servers:
            return options

        allowed_tools = list(getattr(options, "allowed_tools", []) or [])
        known_tools = set(allowed_tools)

        for server_name, mcp_server in mcp_servers.items():
            tools = await list_tools(server_name, mcp_server)
            for tool in tools:
                if tool not in known_tools:
                    allowed_tools.append(tool)
                    known_tools.add(tool)

        current_allowed = getattr(options, "allowed_tools", None)
        if isinstance(current_allowed, list):
            current_allowed[:] = allowed_tools
        elif current_allowed is None:
            try:
                options.allowed_tools = allowed_tools  # type: ignore[assignment]
            except AttributeError:
                try:
                    setattr(options, "allowed_tools", allowed_tools)
                except AttributeError:
                    pass
        else:
            try:
                options.allowed_tools = allowed_tools  # type: ignore[assignment]
            except AttributeError:
                pass
        return options


    def _format_message(self, message: Any) -> Optional[str]:
        if isinstance(message, AssistantMessage) or isinstance(message, UserMessage):
            role = "assistant" if isinstance(message, AssistantMessage) else "user"
            fragments = [self._format_block(block) for block in message.content]
            if fragments:
                return f"{role}: {' | '.join(fragments)}"
            return f"{role}: <no blocks>"

        return None
    
    def _format_block(self, block: ContentBlock) -> str:
        if isinstance(block, TextBlock):
            return block.text
        if isinstance(block, ThinkingBlock):
            return block.thinking
        if isinstance(block, ToolUseBlock):
            args = ", ".join(f"{k}: {v}" for k, v in block.input.items())
            return f"Tool call {block.id}, {block.name}({args})"
        if isinstance(block, ToolResultBlock):
            content = block.content if isinstance(block.content, str) else json.dumps(block.content, indent=2)
            content = content if len(content) < 300 else content[:300] + '...'
            return f"Tool call {block.tool_use_id} successfully completed:\n{content}" if not block.is_error else f"Tool call {block.tool_use_id} failed, reason: {content if len(content) > 0 else 'No content'}"
        return ""


async def list_tools(server_name: str, mcp: Any) -> List[str]:
    """
    List available tools from an MCP tool/server.

    Supports stdio, HTTP, and SDK servers.

    Args:
        server_name: Name of the MCP server
        mcp: MCP server configuration

    Returns:
        List of tool names
    """

    server_type = _get_mcp_field(mcp, "type", "")
    if server_type == "stdio":
        params = StdioServerParameters(
            command=_get_mcp_field(mcp, "command", ""),
            args=_get_mcp_field(mcp, "args", []),
            env=_get_mcp_field(mcp, "env", {}),
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                return _convert_to_tool_names(tools_response, server_name)
    elif server_type == "http":
        async with streamablehttp_client(_get_mcp_field(mcp, "url", "")) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                return _convert_to_tool_names(tools_response, server_name)
    elif server_type == "sdk":
        instance: McpServer | None = _get_mcp_field(mcp, "instance", None)
        if instance is None:
            instance = _get_mcp_field(mcp, "server", None)
        if instance is None:
            return []
        list_tools_handler = instance.request_handlers.get(types.ListToolsRequest)
        if list_tools_handler is None:
            return []
        tools_response = await list_tools_handler(None)
        payload = getattr(tools_response, "root", tools_response)
        return _convert_to_tool_names(payload, server_name)
    else:
        return []


def _convert_to_tool_names(tools_response, server_name: str) -> List[str]:
    """Convert MCP tools response to tool names."""
    tools = getattr(tools_response, "tools", None)
    if tools is None and isinstance(tools_response, Mapping):
        tools = tools_response.get("tools", [])
    if not tools:
        return []
    return [f"mcp__{server_name}__{getattr(mcp_tool, 'name', mcp_tool)}" for mcp_tool in tools]


def _print_verbose_message(message: str) -> None:
    """Write a framed message to stderr for better visibility."""
    if not message:
        return

    lines = [line.rstrip() for line in message.splitlines()] or ["<empty message>"]
    width = max(len(line) for line in lines)
    border = "+" + "-" * (width + 4) + "+"

    print(border, file=sys.stderr)
    for line in lines:
        print(f"|  {line.ljust(width)}  |", file=sys.stderr)
    print(border, file=sys.stderr)
    sys.stderr.flush()

__all__ = ["BaseTool", "tool", "Agent"]
