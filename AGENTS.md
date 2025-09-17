# Repository Guidelines

## Project Structure & Module Organization
Python 3.12 project with runtime code in `src/`. Agents that talk to Claude now live in `src/agent/` (`snippet_extractor.py`, `prompt.py`), shared storage helpers in `src/snippet/`, and IO/utilities in `src/utils/`. `main.py` wires everything into a CLI. Keep new modules under the closest matching package; add integration demos or fixtures under `samples/`, not in `src/`.


## Environment & Configuration
Install dependencies with `uv sync` (or `pip install -e .`) from the repo root. Export `CLAUDE_CODE_OAUTH_TOKEN` before running the extractor; fail fast if it is missing. Respect the default 1 MB file cap and exclude test fixtures unless `--include-tests` is passed.

## Build, Test, and Development Commands
- `uv run python main.py <path> --top-n 10` — scan a file or directory and stream snippets to stdout.
- `uv run python main.py samples --output snippets.txt` — write formatted snippets to a file (helpful for manual QA).
- `uv run python -m pytest` — placeholder; add tests here when a `tests/` package exists.
Wrap long runs with `CLAUDE_CODE_OAUTH_TOKEN=... uv run ...` when scripting.

## Coding Style & Naming Conventions
Follow standard Black-compatible formatting (4-space indent, double quotes for docstrings). Type hints are expected on public call surfaces. Loggers use `logging.getLogger("snippet_extractor")`; reuse it for new components. Class names are `PascalCase`, functions `snake_case`, constants `UPPER_SNAKE`. Prefer dataclasses or `NamedTuple` for structured payloads.

## Testing Guidelines
There is no test suite yet; seed `tests/` with pytest modules mirroring the package layout (`tests/utils/test_file_loader.py`). Name async fixtures with the `_event_loop` fixture when needed. Target high-value behaviors: file filtering edge cases, storage serialization, and concurrency guard rails. Keep sample fixtures under `samples/` to avoid polluting the CLI path.

## Commit & Pull Request Guidelines
History favors short, imperative commit subjects (“Add tqdm progress bars…”). Group related changes; avoid multi-purpose commits. Format multiline commit messages with a single `git commit -m $'Title\n\nBody'` invocation instead of repeated `-m` flags or literal `\n`. PRs should state intent, list manual test commands, and mention follow-up work. Link issues when available and attach terminal captures for CLI changes. Request review when the AGENT CLI handles at least one real path end-to-end.
