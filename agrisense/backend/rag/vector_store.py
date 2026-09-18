"""
vector_store.py — Chroma-backed persistent vector store for AgriSense RAG.

The index is persisted to disk at CHROMA_DIR so ingest only runs once.
At query time the store is loaded from disk — no re-embedding needed.

Collection schema (metadata stored per chunk):
    source: str   — filename of origin document
    index:  int   — chunk index within that document
    text:   str   — raw chunk text (stored for retrieval without a separate lookup)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import chromadb
from chromadb.config import Settings

# Persist index next to this file: agrisense/backend/rag/chroma_index/
_CHROMA_DIR = str(Path(__file__).parent / "chroma_index")
_COLLECTION_NAME = "agrisense_kb"


def _get_chroma_client(persist_dir: str | None = None) -> chromadb.PersistentClient:
    """Return a PersistentClient pointed at persist_dir (defaults to _CHROMA_DIR)."""
    dir_path = persist_dir or _CHROMA_DIR
    os.makedirs(dir_path, exist_ok=True)
    return chromadb.PersistentClient(path=dir_path)


def build_index(
    chunks: list[dict],
    embeddings: list[list[float]],
    persist_dir: str | None = None,
) -> chromadb.Collection:
    """
    Build (or rebuild) the Chroma collection from pre-computed embeddings.

    Args:
        chunks:     List of chunk dicts from chunker.load_knowledge_base().
        embeddings: Parallel list of 1024-dim vectors from embedder.embed_batch().
        persist_dir: Override for the Chroma persistence directory.

    Returns:
        The Chroma Collection object.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must be the same length"
        )

    client = _get_chroma_client(persist_dir)

    # Drop existing collection if present so we can do a clean rebuild
    existing = [c.name for c in client.list_collections()]
    if _COLLECTION_NAME in existing:
        client.delete_collection(_COLLECTION_NAME)
        print(f"  Dropped existing collection '{_COLLECTION_NAME}'")

    collection = client.create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Chroma requires string IDs; use "source__index" for easy debugging
    ids = [f"{c['source']}__{c['index']}" for c in chunks]
    metadatas = [{"source": c["source"], "index": c["index"]} for c in chunks]
    documents = [c["text"] for c in chunks]

    # Chroma accepts batches; keep batch size ≤ 5000 to stay safe
    BATCH = 500
    for start in range(0, len(chunks), BATCH):
        collection.add(
            ids=ids[start:start + BATCH],
            embeddings=embeddings[start:start + BATCH],
            documents=documents[start:start + BATCH],
            metadatas=metadatas[start:start + BATCH],
        )
        print(f"  Indexed chunks {start}–{min(start + BATCH, len(chunks)) - 1}")

    print(f"Index built: {collection.count()} chunks in '{_COLLECTION_NAME}'")
    return collection


def load_collection(persist_dir: str | None = None) -> chromadb.Collection:
    """
    Load an existing Chroma collection from disk.

    Raises:
        ValueError: if the collection doesn't exist (run ingest.py first).
    """
    client = _get_chroma_client(persist_dir)
    existing = [c.name for c in client.list_collections()]
    if _COLLECTION_NAME not in existing:
        raise ValueError(
            f"Collection '{_COLLECTION_NAME}' not found in {persist_dir or _CHROMA_DIR}. "
            "Run `python -m agrisense.backend.rag.ingest` first."
        )
    return client.get_collection(_COLLECTION_NAME)


def query_collection(
    collection: chromadb.Collection,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Query the vector store and return the top-k most relevant chunks.

    Args:
        collection:      Chroma Collection object.
        query_embedding: 1024-dim query vector.
        top_k:           Number of results to return.

    Returns:
        List of dicts: {"text": str, "source": str, "distance": float}
        Sorted by ascending cosine distance (lower = more similar).
    """
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "distance": round(dist, 4),
        })

    return output
