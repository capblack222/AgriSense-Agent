"""
ingest.py — One-time script to build the Chroma vector index from knowledge base docs.

Run once (or whenever knowledge base files are updated):

    cd agrisense
    python -m backend.rag.ingest

    # Or with an explicit KB dir / persist dir:
    python -m backend.rag.ingest --kb-dir /path/to/kb --chroma-dir /path/to/chroma

What this does:
    1. Loads all .txt files from knowledge_base/
    2. Chunks each file into overlapping segments (~600 chars)
    3. Embeds each chunk via AWS Bedrock Titan Embeddings V2
    4. Stores embeddings + chunk text in a persistent Chroma collection

Requirements:
    - AWS credentials configured (aws configure or env vars)
    - Bedrock access granted for amazon.titan-embed-text-v2:0 in us-east-1
    - `pip install boto3 chromadb` (add these to requirements.txt)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running as `python -m backend.rag.ingest` from the agrisense/ directory
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent.parent.parent))

from agrisense.backend.rag.chunker import load_knowledge_base
from agrisense.backend.rag.embedder import embed_batch
from agrisense.backend.rag.vector_store import build_index


def main():
    parser = argparse.ArgumentParser(description="Build AgriSense RAG index")
    parser.add_argument(
        "--kb-dir",
        default=None,
        help="Path to knowledge base directory (default: agrisense/knowledge_base/)",
    )
    parser.add_argument(
        "--chroma-dir",
        default=None,
        help="Path to Chroma persist directory (default: agrisense/backend/rag/chroma_index/)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("AgriSense RAG Ingest")
    print("=" * 60)

    # ── Step 1: Load and chunk knowledge base ──────────────────────────────────
    print("\n[1/3] Loading and chunking knowledge base...")
    t0 = time.time()
    chunks = load_knowledge_base(kb_dir=args.kb_dir)
    print(f"  Done in {time.time() - t0:.1f}s — {len(chunks)} total chunks")

    # ── Step 2: Embed all chunks via Bedrock ───────────────────────────────────
    print(f"\n[2/3] Embedding {len(chunks)} chunks via AWS Bedrock Titan V2...")
    print("  (This will take ~1-3 minutes depending on Bedrock API latency)")
    t0 = time.time()
    texts = [c["text"] for c in chunks]
    embeddings = embed_batch(texts)
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s — {len(embeddings)} embeddings, {len(embeddings[0])} dims each")

    # ── Step 3: Build Chroma index ─────────────────────────────────────────────
    print("\n[3/3] Building Chroma vector index...")
    t0 = time.time()
    collection = build_index(chunks, embeddings, persist_dir=args.chroma_dir)
    print(f"  Done in {time.time() - t0:.1f}s")

    print("\n" + "=" * 60)
    print(f"✅ Ingest complete! {collection.count()} chunks indexed.")
    print("   To use the retriever:")
    print("   from agrisense.backend.rag import Retriever")
    print('   r = Retriever()')
    print('   print(r.retrieve("wheat irrigation heat stress"))')
    print("=" * 60)


if __name__ == "__main__":
    main()
