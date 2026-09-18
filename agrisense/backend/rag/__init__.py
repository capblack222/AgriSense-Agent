"""
RAG (Retrieval-Augmented Generation) pipeline for AgriSense.

Provides crop-management knowledge retrieval using:
- AWS Bedrock Titan Embeddings V2 for vector encoding
- Chroma for local persistent vector store

Public API:
    from agrisense.backend.rag import Retriever
    retriever = Retriever()
    results = retriever.retrieve("wheat irrigation flowering stage", top_k=5)
"""

from .retriever import Retriever

__all__ = ["Retriever"]
