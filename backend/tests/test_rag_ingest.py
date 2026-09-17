import json
from pathlib import Path

from backend.app.rag.ingest import ingest_guideline_corpus, list_guideline_chunks


def test_ingest_and_list():
    repo_root = Path(__file__).resolve().parents[2]
    guidelines_dir = repo_root / "data" / "guidelines"
    # ensure ingest runs
    n1 = ingest_guideline_corpus(str(guidelines_dir))
    assert n1 > 0
    chunks = list_guideline_chunks()
    assert any(c.topic == "diabetes" and "HbA1c" in c.text for c in chunks)
    # LICENSE.md should not be a source
    assert not any(c.source.lower() == "license.md" for c in chunks)
    # idempotent: running ingest twice does not duplicate ids
    n2 = ingest_guideline_corpus(str(guidelines_dir))
    assert n2 == n1
    chunks2 = list_guideline_chunks()
    ids = [c.id for c in chunks2]
    assert len(ids) == len(set(ids))
