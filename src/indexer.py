"""Codebase indexing via AST parsing."""

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from .types import CodeIndex, SymbolInfo

if TYPE_CHECKING:
    from ast import AST, FunctionDef, AsyncFunctionDef


def _get_signature(node: "FunctionDef | AsyncFunctionDef") -> str:
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


def _get_docstring(node: "AST") -> str:
    """Extract docstring from an AST node."""
    try:
        doc = ast.get_docstring(node)
        return doc or ""
    except Exception:
        return ""


def _extract_usages(tree: "AST", filepath: str, index: CodeIndex):
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
                "line": getattr(node, "lineno", 0),
            })


def index_codebase(root: str) -> CodeIndex:
    """Index all Python files in the given root directory."""
    idx = CodeIndex()
    root_path = Path(root).resolve()
    py_files = sorted(root_path.rglob("*.py"))

    # Collect all source files
    for path in py_files:
        rel = str(path.relative_to(root_path))
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        idx.files[rel] = source
        idx.file_tree.append(rel)

    # Parse each file
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

    return idx
