"""Code Intelligence MCP Server - Package Entry Point

Allows running via: python -m src
Also enables uvx code-intelligence-mcp to work after package installation.
"""

import asyncio
import argparse
import sys
from typing import Any

import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent

from src.indexer import index_codebase
from src.search import setup_bm25_index
from src.tools import create_tools, handle_tool
from src.types import CodeIndex


def build_server(index: CodeIndex, project_root: str) -> Server:
    """Build the MCP server with all tools."""
    server = Server("code-intelligence")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return create_tools(index, project_root)

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        return handle_tool(name, arguments, index, project_root)

    return server


async def main(root: str):
    """Main entry point: index codebase and run MCP server."""
    print(f"[code-intel] Indexing: {root}", file=sys.stderr)
    index = index_codebase(root)

    print(f"[code-intel] Setting up BM25 search index...", file=sys.stderr)
    setup_bm25_index(index)

    print(
        f"[code-intel] Done — {len(index.files)} files, "
        f"{len(index.symbols)} symbols, "
        f"{len(index.bm25_chunks)} BM25 chunks",
        file=sys.stderr,
    )

    server = build_server(index, root)

    async with mcp.server.stdio.stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Code Intelligence MCP Server")
    parser.add_argument("--root", required=True, help="Path to your Python project")
    args = parser.parse_args()

    asyncio.run(main(args.root))
