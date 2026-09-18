"""
embedder.py — Embed text using AWS Bedrock Titan Embeddings V2.

Model: amazon.titan-embed-text-v2:0
Output: 1024-dimensional float vectors
Region: us-east-1

Credentials are loaded from the environment / ~/.aws/credentials the same way
boto3 always does. No extra configuration needed if the user has already run
`aws configure` or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars.
"""

from __future__ import annotations

import json
import os
from typing import Sequence

import boto3

_MODEL_ID = "amazon.titan-embed-text-v2:0"
_REGION = os.getenv("AWS_REGION", "us-east-1")
_EMBEDDING_DIM = 1024

# Module-level client — created lazily so import doesn't fail when boto3 is absent
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=_REGION)
    return _client


def embed_text(text: str) -> list[float]:
    """
    Embed a single string and return a 1024-dim float vector.

    Args:
        text: The input string. Titan V2 accepts up to 8192 tokens.

    Returns:
        List of 1024 floats.

    Raises:
        Exception: Propagates boto3 ClientError on permission / quota issues.
    """
    client = _get_client()
    body = json.dumps({"inputText": text})
    response = client.invoke_model(
        modelId=_MODEL_ID,
        body=body,
        accept="application/json",
        contentType="application/json",
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def embed_batch(texts: Sequence[str]) -> list[list[float]]:
    """
    Embed a list of strings, one Bedrock call per string.

    Titan V2 doesn't support batching in a single API call, so this loops.
    For large knowledge bases consider adding retry/backoff here.

    Args:
        texts: Sequence of strings to embed.

    Returns:
        List of 1024-dim float vectors, same order as input.
    """
    embeddings = []
    for i, text in enumerate(texts):
        vec = embed_text(text)
        embeddings.append(vec)
        if (i + 1) % 10 == 0:
            print(f"  Embedded {i + 1}/{len(texts)} chunks...")
    return embeddings
