# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based code snippet extraction tool that uses the Claude ADK (claude-adk) to analyze source code files and extract valuable, reusable code patterns. The tool integrates with Claude's API to identify library usage patterns, best-practice implementations, and other educational code snippets.

## Development Environment

**Python Version**: Requires Python >=3.12  
**Package Manager**: Uses `uv` for dependency management  
**Main Dependency**: `claude-adk>=0.1.2`

## Key Architecture

The project follows a modular architecture with three core components:

1. **SnippetExtractor** (`src/snippet_extractor.py`): Main orchestration class that coordinates between file reading, Claude ADK agent creation, and the snippet storage tool
2. **SnippetStorage** (`src/snippet_storage.py`): A Claude ADK tool that acts as structured storage for extracted snippets, implementing the `add_snippet` method
3. **Prompt System** (`src/prompt.py`): Contains the system prompt and user prompt templates that guide Claude's snippet extraction behavior

The tool operates by creating a SnippetStorage tool instance, initializing a Claude ADK Agent with this tool, and then running the agent against source code content to extract structured snippets.

## Environment Setup

**Required**: Set `CLAUDE_CODE_OAUTH_TOKEN` environment variable for Claude API authentication.

## Common Commands

**Run snippet extraction**:
```bash
python main.py <file_path> [--top-n N] [--output output_file]
```

**Install dependencies**:
```bash
uv sync
```

**Run with sample file**:
```bash
python main.py samples/test_sample.py --top-n 5
```

## Code Patterns

- The project uses async/await patterns internally but provides a sync wrapper (`extract_snippets_sync`) for the main interface
- Error handling follows a structured approach returning dictionaries with `success`, `response`, and optional `error` fields
- The SnippetStorage tool uses state management to accumulate snippets before formatting them into the final output
- The prompt system is designed to guide Claude to extract specific types of code patterns: library/API usage and best-practice implementations

## Tool Integration

The SnippetStorage class extends BaseTool from claude-adk and uses the `@tool` decorator to expose the `add_snippet` method to Claude. The tool manages its own state and provides methods for output formatting and snippet counting.