"""BM25 search for code search functionality."""

from typing import Any

from rank_bm25 import BM25Okapi

from .types import CodeIndex


def setup_bm25_index(index: CodeIndex) -> None:
    """Build a BM25 search index from the code index.

    Chunks the code by function/class blocks (every 40 lines) for search.
    """
    chunks = []
    for rel, source in index.files.items():
        lines = source.splitlines()
        # Chunk by function/class (every 40 lines)
        chunk_size = 40
        for i in range(0, len(lines), chunk_size):
            block = "\n".join(lines[i:i+chunk_size])
            chunks.append({"text": block, "file": rel, "line": i + 1})

    tokenized = [c["text"].lower().split() for c in chunks]
    index.bm25 = BM25Okapi(tokenized)
    index.bm25_chunks = chunks


def search_code(index: CodeIndex, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search the codebase using BM25 and return top matching snippets."""
    if index.bm25 is None:
        return []

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

    return results
