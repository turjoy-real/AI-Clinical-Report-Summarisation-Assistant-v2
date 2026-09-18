from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import get_settings
from app.graph.workflow import get_graph
from app.logging.observability import metrics
from app.rag.ingest import ingest_guideline_corpus


@pytest.fixture(autouse=True)
def _reset_settings_and_metrics(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("ENABLE_PUBMED", "false")
    monkeypatch.setenv("ENABLE_OPENFDA", "false")
    get_settings.cache_clear()
    get_graph.cache_clear()
    metrics.reset()
    ingest_guideline_corpus(str(get_settings().data_dir / "guidelines"))
    yield
    get_settings.cache_clear()
    get_graph.cache_clear()
    metrics.reset()
