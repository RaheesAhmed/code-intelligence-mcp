"""MCP tool definitions for code intelligence."""

import json
from typing import Any

from mcp.types import Tool, TextContent

from .types import CodeIndex
from .search import search_code



def create_tools(index: CodeIndex, project_root: str) -> list[Tool]:
    """Create all 8 MCP tools for code intelligence."""

    tools = [
        Tool(
            name="get_overview",
            description=(
                "High-level overview of the entire codebase: file tree, total files, "
                "total classes, total functions. Call this FIRST to orient yourself."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_file",
            description="Get the full source of a specific file. Use sparingly — prefer targeted tools.",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative file path"}},
                "required": ["path"],
            },
        ),
        Tool(
            name="find_symbol",
            description=(
                "Look up a class or function by name. Returns its file, line, "
                "docstring, signature, and (for classes) all method signatures."
            ),
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Class or function name"}},
                "required": ["name"],
            },
        ),
        Tool(
            name="search_code",
            description=(
                "Search the codebase by keyword or phrase using BM25. "
                "Returns the top matching code snippets with file + line context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_imports",
            description="Get all imports for a specific file — what modules/names it depends on.",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ),
        Tool(
            name="find_usages",
            description=(
                "Find every location in the codebase where a given name is referenced "
                "(calls, attribute access, variable use)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="list_classes",
            description="List ALL classes in the codebase with their file, line, and method signatures.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="list_functions",
            description="List ALL top-level functions with their file, line, signature, and docstring.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]

    return tools


def handle_tool(name: str, arguments: dict[str, Any], index: CodeIndex, project_root: str) -> list[TextContent]:
    """Handle tool calls and return results."""

    # get_overview
    if name == "get_overview":
        classes = sum(
            1 for syms in index.symbols.values()
            for s in syms if s.kind == "class"
        )
        functions = sum(
            1 for syms in index.symbols.values()
            for s in syms if s.kind == "function"
        )
        result = {
            "project_root": project_root,
            "total_files": len(index.files),
            "total_classes": classes,
            "total_functions": functions,
            "file_tree": index.file_tree,
            "all_symbols": sorted(index.symbols.keys()),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # get_file
    elif name == "get_file":
        path = arguments["path"]
        source = index.files.get(path)
        if source is None:
            return [TextContent(type="text", text=f"File not found: {path}")]
        return [TextContent(type="text", text=f"# {path}\n\n{source}")]

    # find_symbol
    elif name == "find_symbol":
        sym_name = arguments["name"]
        matches = index.symbols.get(sym_name, [])
        if not matches:
            return [TextContent(type="text", text=f"Symbol '{sym_name}' not found.")]
        out = []
        for s in matches:
            entry = {
                "name": s.name,
                "kind": s.kind,
                "file": s.file,
                "line": s.line,
                "signature": s.signature,
                "docstring": s.docstring,
            }
            if s.kind == "class":
                entry["methods"] = s.methods
            out.append(entry)
        return [TextContent(type="text", text=json.dumps(out, indent=2))]

    # search_code
    elif name == "search_code":
        query = arguments["query"]
        top_k = arguments.get("top_k", 5)
        results = search_code(index, query, top_k)
        if not results:
            return [TextContent(type="text", text="No results found.")]
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    # get_imports
    elif name == "get_imports":
        path = arguments["path"]
        imports = index.imports.get(path)
        if imports is None:
            return [TextContent(type="text", text=f"File not found: {path}")]
        return [TextContent(type="text", text=json.dumps({"file": path, "imports": imports}, indent=2))]

    # find_usages
    elif name == "find_usages":
        sym_name = arguments["name"]
        limit = arguments.get("limit", 20)
        usages = index.usages.get(sym_name, [])
        # deduplicate by file+line
        seen = set()
        unique = []
        for u in usages:
            key = (u["file"], u["line"])
            if key not in seen:
                seen.add(key)
                unique.append(u)
        result = {
            "name": sym_name,
            "total_usages": len(unique),
            "usages": unique[:limit],
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # list_classes
    elif name == "list_classes":
        classes = []
        for sym_name, syms in index.symbols.items():
            for s in syms:
                if s.kind == "class":
                    classes.append({
                        "name": s.name,
                        "file": s.file,
                        "line": s.line,
                        "docstring": s.docstring[:200] if s.docstring else "",
                        "methods": s.methods,
                    })
        classes.sort(key=lambda c: (c["file"], c["line"]))
        return [TextContent(type="text", text=json.dumps(classes, indent=2))]

    # list_functions
    elif name == "list_functions":
        funcs = []
        for sym_name, syms in index.symbols.items():
            for s in syms:
                if s.kind == "function":
                    funcs.append({
                        "name": s.name,
                        "signature": s.signature,
                        "file": s.file,
                        "line": s.line,
                        "docstring": s.docstring[:200] if s.docstring else "",
                    })
        funcs.sort(key=lambda f: (f["file"], f["line"]))
        return [TextContent(type="text", text=json.dumps(funcs, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]
