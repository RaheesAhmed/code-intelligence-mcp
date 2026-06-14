"""Data structures for code indexing."""

from typing import Optional

from rank_bm25 import BM25Okapi


class SymbolInfo:
    """Represents a code symbol (class, function, or method)."""

    def __init__(
        self,
        name: str,
        kind: str,
        file: str,
        line: int,
        docstring: str = "",
        signature: str = "",
        methods: Optional[list[str]] = None,
    ):
        self.name = name
        self.kind = kind  # "class" | "function" | "method"
        self.file = file
        self.line = line
        self.docstring = docstring
        self.signature = signature
        self.methods = methods or []  # for classes


class CodeIndex:
    """In-memory index of a Python codebase."""

    def __init__(self):
        self.symbols: dict[str, list[SymbolInfo]] = {}  # name -> list of defs
        self.files: dict[str, str] = {}  # path -> source code
        self.imports: dict[str, list[str]] = {}  # file -> list of imported names
        self.usages: dict[str, list[dict]] = {}  # name -> [{file, line}]
        self.bm25: Optional[BM25Okapi] = None
        self.bm25_chunks: list[dict] = []  # [{text, file, line}]
        self.file_tree: list[str] = []
