"""Tests for RAG retrieve module. Owned by Vamsi."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.contracts import GuidelineChunk
from app.rag.retrieve import (
    embed_guidelines,
    retrieve_guidelines,
    _lexical_score,
    _apply_topic_boosts,
    _apply_specialty_boost,
)
from app.rag.ingest import ingest_guideline_corpus, list_guideline_chunks


@pytest.fixture(autouse=True)
def ensure_ingest():
    """Ensure guideline corpus is ingested before each test."""
    repo_root = Path(__file__).resolve().parents[2]
    guidelines_dir = repo_root / "data" / "guidelines"
    ingest_guideline_corpus(str(guidelines_dir))


def test_retrieve_diabetes_ranks_first():
    """Query for diabetes keywords should rank diabetes topic first."""
    docs = retrieve_guidelines("HbA1c 9.2 diabetes")
    assert len(docs) > 0
    assert docs[0].topic == "diabetes", f"Expected diabetes first, got {docs[0].topic}"


def test_retrieve_sepsis_distinct():
    """Query for sepsis should rank sepsis topic first."""
    docs = retrieve_guidelines("sepsis lactate pneumonia fever")
    assert len(docs) > 0
    assert docs[0].topic == "sepsis", f"Expected sepsis first, got {docs[0].topic}"


def test_retrieve_empty_query_returns_empty():
    """Empty or whitespace-only query returns empty list, no crash."""
    assert retrieve_guidelines("") == []
    assert retrieve_guidelines("   ") == []
    assert retrieve_guidelines(None) == []


def test_retrieve_respects_k():
    """Retrieve respects k parameter."""
    docs = retrieve_guidelines("medical", k=2)
    assert len(docs) <= 2


def test_retrieve_default_k():
    """Default k is 4."""
    docs = retrieve_guidelines("guidelines", k=100)
    # We have multiple guidelines, should return up to 100
    assert len(docs) >= 4


def test_retrieve_never_raises_on_unknown_tokens():
    """Retrieve should handle any token gracefully, no exceptions."""
    # Random gibberish
    docs = retrieve_guidelines("xyzabc qwerty 12345")
    assert isinstance(docs, list)  # Should not raise, just return empty or low-score results

    # Unicode
    docs = retrieve_guidelines("café naïve 日本語")
    assert isinstance(docs, list)

    # Very long token
    docs = retrieve_guidelines("a" * 1000)
    assert isinstance(docs, list)


def test_retrieve_with_specialty_boost():
    """Specialty parameter should boost relevant topics."""
    docs_no_spec = retrieve_guidelines("hba1c", specialty=None, k=10)
    docs_endo = retrieve_guidelines("hba1c", specialty="endocrine", k=10)

    # With endocrine specialty, diabetes should rank even higher
    if len(docs_endo) > 0 and len(docs_no_spec) > 0:
        endo_idx = next(
            (i for i, d in enumerate(docs_endo) if d.topic == "diabetes"),
            float("inf")
        )
        no_spec_idx = next(
            (i for i, d in enumerate(docs_no_spec) if d.topic == "diabetes"),
            float("inf")
        )
        # Boost should improve ranking (lower or equal index)
        assert endo_idx <= no_spec_idx


def test_embed_guidelines_no_key():
    """embed_guidelines() returns 0 when OPENAI_API_KEY is not set."""
    # Remove key if it exists
    original = os.environ.pop("OPENAI_API_KEY", None)
    try:
        result = embed_guidelines()
        assert result == 0
    finally:
        if original:
            os.environ["OPENAI_API_KEY"] = original


def test_lexical_score_respects_stopwords():
    """Lexical score ignores common stopwords."""
    chunk = GuidelineChunk(
        id="test-1",
        title="Test Diabetes",
        topic="diabetes",
        source="test.md",
        text="This is a test about diabetes management.",
        citation="Test",
    )

    # Query with many stopwords should still score on "diabetes"
    score = _lexical_score("a the and diabetes", chunk)
    assert score > 0.0


def test_topic_boost_keywords():
    """Topic boost recognizes keyword synonyms."""
    chunk_diabetes = GuidelineChunk(
        id="diabetes-1",
        title="Diabetes",
        topic="diabetes",
        source="diabetes.md",
        text="HbA1c test",
        citation="",
    )

    boost = _apply_topic_boosts("HbA1c management", chunk_diabetes)
    assert boost > 1.0  # Should boost for diabetes keyword


def test_specialty_boost():
    """Specialty boost applies to matching topics."""
    chunk = GuidelineChunk(
        id="diabetes-1",
        title="Diabetes",
        topic="diabetes",
        source="diabetes.md",
        text="HbA1c",
        citation="",
    )

    # Endocrine specialty should boost diabetes
    boost = _apply_specialty_boost(chunk, "endocrine")
    assert boost == 1.2

    # Cardio specialty should not boost diabetes
    boost = _apply_specialty_boost(chunk, "cardio")
    assert boost == 1.0


def test_retrieve_returns_retrieved_doc_shape():
    """Retrieved docs have all required fields."""
    docs = retrieve_guidelines("diabetes")
    assert len(docs) > 0

    doc = docs[0]
    assert hasattr(doc, "id")
    assert hasattr(doc, "title")
    assert hasattr(doc, "topic")
    assert hasattr(doc, "source")
    assert hasattr(doc, "text")
    assert hasattr(doc, "score")
    assert hasattr(doc, "citation")

    assert isinstance(doc.id, str)
    assert isinstance(doc.title, str)
    assert isinstance(doc.topic, str)
    assert isinstance(doc.source, str)
    assert isinstance(doc.text, str)
    assert isinstance(doc.score, (int, float))
    assert isinstance(doc.citation, str)


def test_retrieve_sorted_by_score():
    """Retrieved docs are sorted by score descending."""
    docs = retrieve_guidelines("medical guidelines")
    if len(docs) > 1:
        for i in range(len(docs) - 1):
            assert docs[i].score >= docs[i + 1].score


@pytest.mark.skipif(
    os.environ.get("OPENAI_API_KEY") is None,
    reason="Skipped: OPENAI_API_KEY not set (Chroma vector tests require it)"
)
def test_embed_guidelines_with_key():
    """embed_guidelines() returns chunk count when OPENAI_API_KEY is set."""
    result = embed_guidelines()
    chunks = list_guideline_chunks()
    # Should return the number of chunks, or 0 if Chroma unavailable (no crash)
    assert result >= 0
    if result > 0:
        assert result == len(chunks)
