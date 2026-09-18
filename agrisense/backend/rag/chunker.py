"""
chunker.py — Load knowledge base text files and split into overlapping chunks.

Strategy:
  - Split on paragraph boundaries (\n\n) first
  - If a paragraph exceeds MAX_CHARS, split further on sentence boundaries
  - Add OVERLAP_CHARS of context from the previous chunk to each chunk
  - Tag each chunk with metadata: source filename + chunk index

Tuning:
  MAX_CHARS   = 600  (fits comfortably within Bedrock Titan V2's 8192-token input limit)
  OVERLAP_CHARS = 50 (enough context to keep split sentences coherent)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterator

MAX_CHARS = 600
OVERLAP_CHARS = 50

# Default knowledge-base directory relative to this file's location
_KB_DIR = Path(__file__).parent.parent.parent / "knowledge_base"


def _iter_paragraphs(text: str) -> Iterator[str]:
    """Yield non-empty paragraphs from raw text."""
    for para in re.split(r"\n{2,}", text):
        para = para.strip()
        if para:
            yield para


def _split_long_paragraph(para: str) -> list[str]:
    """
    Split a paragraph that exceeds MAX_CHARS into sentence-sized chunks.
    Sentences are identified by period/question-mark/exclamation followed by whitespace.
    """
    if len(para) <= MAX_CHARS:
        return [para]

    sentences = re.split(r"(?<=[.!?])\s+", para)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= MAX_CHARS:
            current = (current + " " + sentence).strip() if current else sentence
        else:
            if current:
                chunks.append(current)
            # If a single sentence is longer than MAX_CHARS, keep it as-is
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def chunk_text(text: str, source: str) -> list[dict]:
    """
    Convert raw document text into a list of chunk dicts.

    Each dict has:
        {
            "text":   str,   # chunk content (possibly with overlap prefix)
            "source": str,   # filename of origin
            "index":  int,   # sequential chunk index within document
        }
    """
    raw_chunks: list[str] = []
    for para in _iter_paragraphs(text):
        raw_chunks.extend(_split_long_paragraph(para))

    chunks: list[dict] = []
    for i, chunk in enumerate(raw_chunks):
        # Prepend tail of the previous chunk for context overlap
        if i > 0 and OVERLAP_CHARS > 0:
            overlap = raw_chunks[i - 1][-OVERLAP_CHARS:]
            text_with_overlap = overlap + " " + chunk
        else:
            text_with_overlap = chunk

        chunks.append({
            "text": text_with_overlap,
            "source": source,
            "index": i,
        })

    return chunks


def load_knowledge_base(kb_dir: str | Path | None = None) -> list[dict]:
    """
    Load all .txt files from the knowledge base directory and return chunks.

    Args:
        kb_dir: Path to directory containing .txt knowledge files.
                Defaults to agrisense/knowledge_base/.

    Returns:
        List of chunk dicts across all loaded files.
    """
    kb_path = Path(kb_dir) if kb_dir else _KB_DIR
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base directory not found: {kb_path}")

    all_chunks: list[dict] = []
    txt_files = sorted(kb_path.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {kb_path}")

    for txt_file in txt_files:
        text = txt_file.read_text(encoding="utf-8")
        chunks = chunk_text(text, source=txt_file.name)
        all_chunks.extend(chunks)
        print(f"  Loaded {txt_file.name}: {len(chunks)} chunks")

    print(f"Total chunks across all documents: {len(all_chunks)}")
    return all_chunks
