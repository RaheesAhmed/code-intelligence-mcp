# Code Intelligence MCP Server

A Model Context Protocol (MCP) server that indexes Python codebases and exposes intelligent tools for code exploration and search.

## Overview

This server analyzes a Python project at startup, building an in-memory index that includes:
- **AST parsing**: Extracts classes, functions, methods with signatures and docstrings
- **Import tracking**: Maps what each file imports
- **Usage tracking**: Finds where symbols are referenced throughout the codebase
- **BM25 search**: Full-text keyword search across all code

The indexed data powers 8 MCP tools that let an AI assistant navigate and query codebases semantically.

## Quick Start (uvx)

Run directly without installing:

```powershell
uvx code-intelligence-mcp --root D:\path\to\your\project
```

> **Note**: On Windows, use double backslashes or forward slashes for paths.

## Directory Structure

```
code_intelligence_mcp/
├── main.py                 # Entry point - run this to start the server
├── mcp_client.py           # Test client that connects to the server
├── pyproject.toml          # Package configuration
├── README.md               # This file
├── src/
│   ├── __init__.py         # Package exports
│   ├── __main__.py         # Package entry point (for python -m src)
│   ├── types.py            # SymbolInfo, CodeIndex data classes
│   ├── indexer.py          # AST parsing and codebase indexing
│   ├── search.py           # BM25 search setup and search logic
│   └── tools.py            # MCP tool definitions (create_tools, handle_tool)
└── code_intelligence.py    # Original monolithic file (kept for reference)
```

## Requirements

- Python 3.12+
- `uv` package manager
- Dependencies (installed in project virtual environment):
  - `langchain-mcp-adapters>=0.3.0`
  - `mcp>=1.27.2`
  - `rank-bm25>=0.2.2`

## Install Dependencies

From the repo root:

```powershell
uv add mcp rank-bm25
```

If you already have them installed, skip this step.

## Run the MCP Server

### Option 1: uvx (recommended for quick testing)

```powershell
uvx code-intelligence-mcp --root D:\path\to\your\project
```

### Option 2: Local development

```powershell
cd code_intelligence_mcp
uv run python main.py --root D:\path\to\your\project
```

### Option 3: python -m src

```powershell
cd code_intelligence_mcp
uv run python -m src --root D:\path\to\your\project
```

> **Note**: On Windows, pass the root path with normal backslashes and use `uv run python` instead of calling `uv` directly as the subprocess command.

The server will print indexing progress and then wait for MCP requests:

```
[code-intel] Indexing: D:\path\to\project
[code-intel] Setting up BM25 search index...
[code-intel] Done — 42 files, 156 symbols, 320 BM25 chunks
```

## MCP Tools

### 1. get_overview
High-level overview of the entire codebase. Call this **first** to orient yourself.

- **Returns**: project root, total files/classes/functions, file tree, all symbol names

### 2. get_file
Get the full source of a specific file by relative path.

- **Arguments**: `path` (string) - relative path to the file
- **Returns**: Full file contents with path header

### 3. find_symbol
Look up a class or function by exact name.

- **Arguments**: `name` (string) - class or function name
- **Returns**: File, line, docstring, signature, and (for classes) method signatures

### 4. search_code
Full-text search using BM25 algorithm - good for finding code by keyword or phrase.

- **Arguments**:
  - `query` (string, required) - search keyword/phrase
  - `top_k` (integer, default=5) - number of results
- **Returns**: Top matching code snippets with scores, file, and line context

### 5. get_imports
Get all imports for a specific file - what modules/names it depends on.

- **Arguments**: `path` (string) - relative path to the file
- **Returns**: List of imported module names

### 6. find_usages
Find every location in the codebase where a given name is referenced (calls, attribute access, variable use).

- **Arguments**:
  - `name` (string, required) - symbol name to find
  - `limit` (integer, default=20) - max results
- **Returns**: Total usage count and list of {file, line} locations

### 7. list_classes
List ALL classes in the codebase with their file, line, and method signatures.

- **Returns**: Array of {name, file, line, docstring, methods} sorted by file/line

### 8. list_functions
List ALL top-level functions with their file, line, signature, and docstring.

- **Returns**: Array of {name, signature, file, line, docstring} sorted by file/line

## Example Usage

### Test with mcp_client.py

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    client = MultiServerMCPClient(
        {
            "project-intel": {
                "transport": "stdio",
                "command": "uv",
                "args": [
                    "run",
                    "python",
                    "main.py",
                    "--root",
                    "D:\\path\\to\\your\\project",
                ],
            }
        }
    )

    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run with:
```powershell
uv run python mcp_client.py
```

## Publishing to PyPI

### Prerequisites

1. Create a PyPI account at https://pypi.org/
2. Create an API token at https://pypi.org/manage/account/
3. Set the token as an environment variable:
   ```powershell
   $env:UV_PUBLISH_TOKEN = "pypi-your-token-here"
   ```

### Build and Publish

```powershell
uv build
uv publish
```

### Install from PyPI

After publishing, users can install and run:

```powershell
# Install globally
uv pip install code-intelligence-mcp

# Or run directly with uvx (recommended)
uvx code-intelligence-mcp --root D:\path\to\your\project
```

## Troubleshooting

- `mcp.shared.exceptions.McpError: Connection closed` usually means the server subprocess failed to start correctly.
- Verify the `uv run python` command works manually before using it inside `mcp_client.py`.
- Ensure the path passed to `--root` is valid and accessible.
- If you get import errors, make sure you're running from the project directory with the correct virtual environment activated.
