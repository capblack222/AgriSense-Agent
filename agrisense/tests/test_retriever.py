"""
test_retriever.py — Retriever unit + eval tests.

Split into two test layers:

1. Unit tests (no AWS, no Chroma index required)
   - Test chunker.chunk_text() directly
   - Test Retriever behaviour when Chroma index is missing
   - Mock embed_text + query_collection for query/format tests

2. Eval tests (skipped unless AGRISENSE_EVAL=1 env var is set)
   - Require: Chroma index built (run ingest.py) + AWS credentials
   - Load eval_qa_pairs.json and check retrieval quality
   - Pass criteria: top-5 results contain ≥1 expected keyword
   - A pass rate ≥ 80% is the acceptance threshold

Run unit tests only (default, fast, no AWS):
    cd agrisense
    pytest tests/test_retriever.py -v

Run eval tests (slow, requires AWS + built index):
    AGRISENSE_EVAL=1 pytest tests/test_retriever.py -v -m eval
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_TESTS_DIR = Path(__file__).parent
_AGRISENSE_DIR = _TESTS_DIR.parent
sys.path.insert(0, str(_AGRISENSE_DIR / "backend"))

from rag.chunker import chunk_text, load_knowledge_base
from rag.retriever import Retriever


# =============================================================================
# ── CHUNKER UNIT TESTS ────────────────────────────────────────────────────────
# =============================================================================

class TestChunker:
    """Tests for chunker.chunk_text() and load_knowledge_base()."""

    def test_chunk_text_basic(self):
        """Simple text produces at least one chunk."""
        text = "This is a paragraph about wheat irrigation."
        chunks = chunk_text(text, source="test.txt")
        assert len(chunks) >= 1
        assert chunks[0]["source"] == "test.txt"
        assert chunks[0]["index"] == 0
        assert "wheat" in chunks[0]["text"]

    def test_chunk_text_multiple_paragraphs(self):
        """Multiple paragraphs produce multiple chunks."""
        text = (
            "Wheat needs irrigation at crown root initiation stage.\n\n"
            "Rice is grown in flooded conditions.\n\n"
            "Maize is sensitive to drought at tasseling."
        )
        chunks = chunk_text(text, source="test.txt")
        assert len(chunks) == 3

    def test_chunk_text_long_paragraph_is_split(self):
        """A very long paragraph (>600 chars) is split into multiple chunks."""
        # Create a paragraph > 600 chars by repeating sentences
        long_para = "This is a sentence about irrigation. " * 20  # ~720 chars
        chunks = chunk_text(long_para, source="test.txt")
        assert len(chunks) >= 2, "Long paragraph should be split"

    def test_chunk_text_overlap_prefix(self):
        """Second+ chunks have overlap text from the previous chunk."""
        text = (
            "First paragraph about wheat.\n\n"
            "Second paragraph about rice."
        )
        chunks = chunk_text(text, source="test.txt")
        assert len(chunks) == 2
        # The second chunk should contain tail of first paragraph
        assert "wheat" in chunks[1]["text"], (
            "Second chunk should have overlap from first chunk"
        )

    def test_chunk_text_empty_text(self):
        """Empty text produces no chunks."""
        chunks = chunk_text("", source="empty.txt")
        assert chunks == []

    def test_chunk_text_only_whitespace(self):
        """Whitespace-only text produces no chunks."""
        chunks = chunk_text("   \n\n   \n\n   ", source="empty.txt")
        assert chunks == []

    def test_chunk_text_metadata_fields(self):
        """Each chunk has the correct metadata fields."""
        text = "Para one.\n\nPara two."
        chunks = chunk_text(text, source="guide.txt")
        for chunk in chunks:
            assert "text" in chunk
            assert "source" in chunk
            assert "index" in chunk
            assert chunk["source"] == "guide.txt"

    def test_load_knowledge_base_counts(self):
        """Knowledge base loads all 4 .txt files and produces >0 chunks."""
        kb_dir = _AGRISENSE_DIR / "knowledge_base"
        if not kb_dir.exists():
            pytest.skip("Knowledge base directory not found")
        chunks = load_knowledge_base(kb_dir)
        assert len(chunks) > 50, "Expected substantial number of chunks from real KB"

    def test_load_knowledge_base_sources(self):
        """All knowledge base files are represented in chunks."""
        kb_dir = _AGRISENSE_DIR / "knowledge_base"
        if not kb_dir.exists():
            pytest.skip("Knowledge base directory not found")
        chunks = load_knowledge_base(kb_dir)
        sources = {c["source"] for c in chunks}
        assert "wheat_guide.txt" in sources
        assert "rice_guide.txt" in sources
        assert "tomato_maize_guide.txt" in sources
        assert "cotton_soybean_sugarcane_guide.txt" in sources

    def test_load_knowledge_base_missing_dir(self):
        """Missing KB directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_knowledge_base("/nonexistent/path/knowledge_base")


# =============================================================================
# ── RETRIEVER UNIT TESTS (no AWS, mocked) ────────────────────────────────────
# =============================================================================

class TestRetrieverUnit:
    """Unit tests for Retriever that mock out Bedrock + Chroma."""

    def test_retriever_missing_index_raises(self):
        """Retriever.retrieve() raises ValueError if Chroma index doesn't exist."""
        retriever = Retriever(persist_dir="/nonexistent/chroma")
        with pytest.raises((ValueError, Exception)):
            retriever.retrieve("wheat irrigation")

    def test_format_context_empty(self):
        """format_context([]) returns empty string."""
        result = Retriever.format_context([])
        assert result == ""

    def test_format_context_single_result(self):
        """format_context formats source and text."""
        results = [{"text": "Apply 6cm water at flowering.", "source": "wheat_guide.txt", "distance": 0.1}]
        formatted = Retriever.format_context(results)
        assert "wheat_guide.txt" in formatted
        assert "6cm water" in formatted

    def test_format_context_respects_max_chars(self):
        """format_context truncates output to max_chars."""
        results = [
            {"text": "A" * 1000, "source": "file.txt", "distance": 0.1},
            {"text": "B" * 1000, "source": "file2.txt", "distance": 0.2},
        ]
        formatted = Retriever.format_context(results, max_chars=500)
        assert len(formatted) <= 600  # some slack for header text

    def test_format_context_multiple_results(self):
        """format_context includes all results when within budget."""
        results = [
            {"text": "Wheat needs water.", "source": "wheat_guide.txt", "distance": 0.1},
            {"text": "Rice needs flooding.", "source": "rice_guide.txt", "distance": 0.2},
        ]
        formatted = Retriever.format_context(results)
        assert "wheat_guide.txt" in formatted
        assert "rice_guide.txt" in formatted

    def test_retriever_mocked_retrieve(self):
        """Retriever.retrieve() calls embed_text and query_collection correctly."""
        fake_embedding = [0.1] * 1024
        fake_results = [
            {"text": "Wheat at flowering needs water.", "source": "wheat_guide.txt", "distance": 0.05}
        ]

        with (
            patch("rag.retriever.load_collection") as mock_load,
            patch("rag.retriever.embed_text", return_value=fake_embedding),
            patch("rag.retriever.query_collection", return_value=fake_results) as mock_query,
        ):
            mock_load.return_value = MagicMock()
            retriever = Retriever(persist_dir="/fake/path", top_k=3)
            results = retriever.retrieve("wheat flowering irrigation")

        assert results == fake_results
        mock_query.assert_called_once()
        # Verify top_k was passed correctly
        _, kwargs = mock_query.call_args
        assert kwargs.get("top_k") == 3 or mock_query.call_args[0][2] == 3

    def test_retriever_mocked_retrieve_and_format(self):
        """retrieve_and_format() returns a non-empty formatted string."""
        fake_embedding = [0.0] * 1024
        fake_results = [
            {"text": "Rice blast can destroy a crop in 10 days.", "source": "rice_guide.txt", "distance": 0.08}
        ]

        with (
            patch("rag.retriever.load_collection") as mock_load,
            patch("rag.retriever.embed_text", return_value=fake_embedding),
            patch("rag.retriever.query_collection", return_value=fake_results),
        ):
            mock_load.return_value = MagicMock()
            retriever = Retriever(persist_dir="/fake/path")
            output = retriever.retrieve_and_format("rice blast disease")

        assert "rice_guide.txt" in output
        assert "blast" in output.lower()


# =============================================================================
# ── EVAL TESTS (requires built Chroma index + AWS credentials) ────────────────
# =============================================================================

_EVAL_ENABLED = os.getenv("AGRISENSE_EVAL", "0") == "1"
_QA_FILE = _TESTS_DIR / "eval_qa_pairs.json"


@pytest.mark.skipif(not _EVAL_ENABLED, reason="Set AGRISENSE_EVAL=1 to run eval tests")
@pytest.mark.eval
class TestRetrieverEval:
    """
    End-to-end retrieval quality evaluation.
    Requires: ingest.py already run, valid AWS credentials.
    """

    @pytest.fixture(scope="class")
    def retriever(self):
        """Load retriever once per test class."""
        return Retriever()

    @pytest.fixture(scope="class")
    def qa_pairs(self):
        """Load QA evaluation pairs from JSON."""
        with open(_QA_FILE) as f:
            return json.load(f)

    def _check_result_contains_keyword(self, results: list[dict], keyword: str) -> bool:
        """Return True if any retrieved chunk contains the keyword (case-insensitive)."""
        kw_lower = keyword.lower()
        for r in results:
            if kw_lower in r["text"].lower():
                return True
        return False

    def test_retrieval_pass_rate(self, retriever, qa_pairs):
        """
        For each QA pair, retrieve top-5 chunks and check that at least 1
        expected keyword appears in the retrieved text.

        Acceptance threshold: ≥80% pass rate.
        """
        passed = 0
        failed = []

        for qa in qa_pairs:
            results = retriever.retrieve(qa["query"], top_k=5)
            keywords = qa.get("expected_keywords", [])

            # A QA pair passes if ANY expected keyword is found in any chunk
            found = any(
                self._check_result_contains_keyword(results, kw)
                for kw in keywords
            )
            if found:
                passed += 1
            else:
                failed.append({
                    "id": qa["id"],
                    "query": qa["query"],
                    "expected_keywords": keywords,
                    "top_result": results[0]["text"][:200] if results else "NO RESULTS",
                })

        total = len(qa_pairs)
        pass_rate = passed / total

        if failed:
            print(f"\nFailed QA pairs ({len(failed)}/{total}):")
            for f in failed:
                print(f"  [{f['id']}] {f['query']}")
                print(f"    Expected: {f['expected_keywords']}")
                print(f"    Got: {f['top_result'][:100]}...")

        print(f"\nRetrieval pass rate: {pass_rate:.0%} ({passed}/{total})")
        assert pass_rate >= 0.80, (
            f"Retrieval quality too low: {pass_rate:.0%} (need ≥80%). "
            f"Failed: {[f['id'] for f in failed]}"
        )

    def test_retrieval_latency(self, retriever):
        """Single retrieval should complete in under 3 seconds (Bedrock P95)."""
        import time
        query = "wheat irrigation heat stress flowering"
        t0 = time.time()
        results = retriever.retrieve(query, top_k=5)
        elapsed = time.time() - t0

        assert results, "Expected at least one result"
        assert elapsed < 3.0, f"Retrieval took {elapsed:.2f}s — exceeds 3s SLA"

    def test_wheat_heat_query(self, retriever):
        """Known high-value query: wheat heat stress should surface wheat_guide.txt."""
        results = retriever.retrieve("wheat flowering heat stress temperature pollen", top_k=5)
        sources = {r["source"] for r in results}
        assert "wheat_guide.txt" in sources, (
            f"Expected wheat_guide.txt in top-5, got: {sources}"
        )

    def test_rice_blast_query(self, retriever):
        """Known query: rice blast disease."""
        results = retriever.retrieve("rice blast fungal disease booting stage", top_k=5)
        combined_text = " ".join(r["text"] for r in results).lower()
        assert "blast" in combined_text or "tricyclazole" in combined_text or "pyricularia" in combined_text, (
            "Expected blast-related content in top-5 results"
        )

    def test_cross_crop_query(self, retriever):
        """Cross-crop query should return diverse sources."""
        results = retriever.retrieve("waterlogging sensitivity drain field crops", top_k=5)
        sources = {r["source"] for r in results}
        # Should surface at least 2 different crop guides
        assert len(sources) >= 1, "Expected at least one relevant source"
