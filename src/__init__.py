"""Code Intelligence MCP Server - Modular Package

This package provides code intelligence tools for indexing and querying
Python codebases via the Model Context Protocol (MCP).
"""

from .types import SymbolInfo, CodeIndex
from .indexer import index_codebase
from .search import setup_bm25_index, search_code
from .tools import create_tools

__all__ = [
    "SymbolInfo",
    "CodeIndex",
    "index_codebase",
    "setup_bm25_index",
    "search_code",
    "create_tools",
]
