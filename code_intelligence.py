"""
Python Code Intelligence MCP Server
------------------------------------
Indexes a Python codebase at startup and exposes smart tools so an AI
can ask deep questions about the code — not just read raw files.

Usage:
  python code_intelligence.py --root /path/to/your/project

Install deps:
  pip install mcp rank-bm25
"""

import ast
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Any
from rank_bm25 import BM25Okapi
import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent

# ─────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────

class SymbolInfo:
    def __init__(self, name, kind, file, line, docstring="", signature="", methods=None):
        self.name = name
        self.kind = kind          # "class" | "function" | "method"
        self.file = file
        self.line = line
        self.docstring = docstring
        self.signature = signature
        self.methods = methods or []   # for classes

class CodeIndex:
    def __init__(self):
        self.symbols: dict[str, list[SymbolInfo]] = {}   # name → list of defs
        self.files: dict[str, str] = {}                  # path → source code
        self.imports: dict[str, list[str]] = {}          # file → list of imported names
        self.usages: dict[str, list[dict]] = {}          # name → [{file, line}]
        self.bm25: BM25Okapi | None = None
        self.bm25_chunks: list[dict] = []                # [{text, file, line}]
        self.file_tree: list[str] = []

# ─────────────────────────────────────────────
#  INDEXER  —  runs once at startup
# ─────────────────────────────────────────────

def _get_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Build a human-readable function signature from an AST node."""
    args = []
    fn_args = node.args
    # positional
    for arg in fn_args.args:
        args.append(arg.arg)
    # *args
    if fn_args.vararg:
        args.append(f"*{fn_args.vararg.arg}")
    # **kwargs
    if fn_args.kwarg:
        args.append(f"**{fn_args.kwarg.arg}")
    return f"{node.name}({', '.join(args)})"


def _get_docstring(node) -> str:
    try:
        doc = ast.get_docstring(node)
        return doc or ""
    except Exception:
        return ""


def _extract_usages(tree: ast.AST, filepath: str, index: CodeIndex):
    """Walk the AST to find all Name and Attribute usages."""
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name:
            if name not in index.usages:
                index.usages[name] = []
            index.usages[name].append({
                "file": filepath,
                "line": getattr(node, "lineno", 0)
            })


def index_codebase(root: str) -> CodeIndex:
    idx = CodeIndex()
    root_path = Path(root).resolve()
    py_files = sorted(root_path.rglob("*.py"))

    # ── Collect all source files ──────────────────────
    for path in py_files:
        rel = str(path.relative_to(root_path))
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        idx.files[rel] = source
        idx.file_tree.append(rel)

    # ── Parse each file ───────────────────────────────
    for rel, source in idx.files.items():
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            continue

        # imports
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.extend(f"{node.module}.{alias.name}" for alias in node.names)
        idx.imports[rel] = imported

        # usages
        _extract_usages(tree, rel, idx)

        # classes and functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # skip if it's a method (parent is ClassDef) — handled below
                sym = SymbolInfo(
                    name=node.name,
                    kind="function",
                    file=rel,
                    line=node.lineno,
                    docstring=_get_docstring(node),
                    signature=_get_signature(node),
                )
                idx.symbols.setdefault(node.name, []).append(sym)

            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(_get_signature(item))
                sym = SymbolInfo(
                    name=node.name,
                    kind="class",
                    file=rel,
                    line=node.lineno,
                    docstring=_get_docstring(node),
                    methods=methods,
                )
                idx.symbols.setdefault(node.name, []).append(sym)

    # ── Build BM25 index (chunk by function/class block) ──
    chunks = []
    for rel, source in idx.files.items():
        lines = source.splitlines()
        # Chunk by function/class (every 40 lines)
        chunk_size = 40
        for i in range(0, len(lines), chunk_size):
            block = "\n".join(lines[i:i+chunk_size])
            chunks.append({"text": block, "file": rel, "line": i + 1})

    tokenized = [c["text"].lower().split() for c in chunks]
    idx.bm25 = BM25Okapi(tokenized)
    idx.bm25_chunks = chunks

    return idx


# ─────────────────────────────────────────────
#  MCP SERVER  —  8 tools
# ─────────────────────────────────────────────

def build_server(index: CodeIndex, project_root: str) -> Server:
    server = Server("code-intelligence")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
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

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:

        # ── get_overview ──────────────────────────────
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

        # ── get_file ──────────────────────────────────
        elif name == "get_file":
            path = arguments["path"]
            source = index.files.get(path)
            if source is None:
                return [TextContent(type="text", text=f"File not found: {path}")]
            return [TextContent(type="text", text=f"# {path}\n\n{source}")]

        # ── find_symbol ───────────────────────────────
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

        # ── search_code ───────────────────────────────
        elif name == "search_code":
            query = arguments["query"]
            top_k = arguments.get("top_k", 5)
            tokens = query.lower().split()
            scores = index.bm25.get_scores(tokens)
            top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
            results = []
            for i in top_idx:
                if scores[i] < 0.01:
                    continue
                chunk = index.bm25_chunks[i]
                results.append({
                    "score": round(float(scores[i]), 3),
                    "file": chunk["file"],
                    "start_line": chunk["line"],
                    "snippet": chunk["text"][:800],
                })
            if not results:
                return [TextContent(type="text", text="No results found.")]
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        # ── get_imports ───────────────────────────────
        elif name == "get_imports":
            path = arguments["path"]
            imports = index.imports.get(path)
            if imports is None:
                return [TextContent(type="text", text=f"File not found: {path}")]
            return [TextContent(type="text", text=json.dumps({"file": path, "imports": imports}, indent=2))]

        # ── find_usages ───────────────────────────────
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

        # ── list_classes ──────────────────────────────
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

        # ── list_functions ────────────────────────────
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

    return server


# ─────────────────────────────────────────────
#  ENTRYPOINT
# ─────────────────────────────────────────────

async def main(root: str):
    print(f"[code-intel] Indexing: {root}", file=sys.stderr)
    index = index_codebase(root)
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
    import asyncio
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Path to your Python project")
    args = parser.parse_args()
    asyncio.run(main(args.root))