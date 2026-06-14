# Code Intelligence MCP Server

This repository contains an MCP server for indexing a Python codebase and exposing code intelligence tools via the Model Context Protocol (MCP).

## What it does

- `code_intelligence.py` indexes a Python project and exposes MCP tools such as:
  - `get_overview`
  - `get_file`
  - `find_symbol`
  - `search_code`
  - `get_imports`
  - `find_usages`
  - `list_classes`
  - `list_functions`

## Requirements

- Python 3.12+
- `uv` package manager
- dependencies installed in this project virtual environment:
  - `langchain-mcp-adapters>=0.3.0`
  - `mcp>=1.27.2`
  - `rank-bm25>=0.2.2`

## Install dependencies

From the repo root:

```powershell
uv add mcp rank-bm25
```

If you already have them in the project environment, skip this step.

## Run the MCP server

Use `uv run python` to start the server subprocess correctly.

```powershell
cd code_intelligence_mcp
uv run python code_intelligence.py --root path-to-project
```

> Note: On Windows, pass the root path with normal backslashes and use `uv run python` instead of calling `uv` directly as the subprocess command.

The server should print indexing progress and then wait for MCP requests.


## Troubleshooting

- `mcp.shared.exceptions.McpError: Connection closed` usually means the server subprocess failed to start correctly.
- Verify the `uv run python` command works manually before using it inside `mcp_client.py`.
- Ensure the path passed to `--root` is valid and accessible.
