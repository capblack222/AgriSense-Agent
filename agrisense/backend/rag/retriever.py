"""
retriever.py — Clean retrieval interface used by agent.py.

Usage:
    from agrisense.backend.rag import Retriever

    retriever = Retriever()                         # loads index from disk
    results = retriever.retrieve("wheat flowering irrigation", top_k=5)
    # [{"text": "...", "source": "wheat_guide.txt", "distance": 0.12}, ...]

    context_str = retriever.format_context(results)  # ready to inject into prompt
"""

from __future__ import annotations

from typing import Sequence

from .embedder import embed_text
from .vector_store import load_collection, query_collection


class Retriever:
    """
    Singleton-friendly retriever that loads the Chroma index once and reuses it.

    The collection is loaded lazily on first call to retrieve() to avoid
    import-time failures if the index hasn't been built yet.
    """

    def __init__(self, persist_dir: str | None = None, top_k: int = 5):
        self._persist_dir = persist_dir
        self._default_top_k = top_k
        self._collection = None  # loaded lazily

    def _ensure_loaded(self):
        if self._collection is None:
            self._collection = load_collection(self._persist_dir)

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        """
        Embed query and return top-k relevant knowledge chunks.

        Args:
            query:  Natural-language question or context string.
            top_k:  Number of results. Defaults to self._default_top_k.

        Returns:
            List of dicts: {"text": str, "source": str, "distance": float}
        """
        self._ensure_loaded()
        k = top_k if top_k is not None else self._default_top_k
        query_vec = embed_text(query)
        return query_collection(self._collection, query_vec, top_k=k)

    @staticmethod
    def format_context(results: list[dict], max_chars: int = 2000) -> str:
        """
        Format retrieval results into a string ready to inject into a prompt.

        Concatenates chunks in order of relevance, truncating at max_chars to
        keep the final prompt within model limits.

        Args:
            results:   Output of retrieve().
            max_chars: Hard cap on total context length.

        Returns:
            Multi-line string of the form:
                [Source: wheat_guide.txt]
                <chunk text>

                [Source: rice_guide.txt]
                <chunk text>
                ...
        """
        lines: list[str] = []
        total = 0
        for r in results:
            chunk_text = f"[Source: {r['source']}]\n{r['text']}"
            if total + len(chunk_text) > max_chars:
                # Truncate this chunk rather than dropping it entirely
                remaining = max_chars - total
                if remaining > 80:  # only add if meaningful
                    lines.append(chunk_text[:remaining] + "…")
                break
            lines.append(chunk_text)
            total += len(chunk_text) + 2  # +2 for \n\n separator

        return "\n\n".join(lines)

    def retrieve_and_format(self, query: str, top_k: int | None = None, max_chars: int = 2000) -> str:
        """Convenience: retrieve then format in one call."""
        results = self.retrieve(query, top_k=top_k)
        return self.format_context(results, max_chars=max_chars)
