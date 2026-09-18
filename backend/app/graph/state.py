from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.logging.observability import metrics, utcnow


class GraphState(TypedDict, total=False):
    thread_id: str
    case_id: str
    raw_text: str
    extracted_text: str
    report_type: str
    specialty: str
    urgency: str
    router_confidence: float
    router_rationale: str
    analysis: dict[str, Any]
    lab_flags: list[dict[str, Any]]
    retrieved_docs: list[dict[str, Any]]
    summary: str
    recommendations: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    used_topics: list[str]
    safety_flags: list[str]
    hitl_required: bool
    human_decision: str
    human_edits: str
    human_feedback: str
    chat_history: list[dict[str, str]]
    errors: Annotated[list[str], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
    model_used: str
    status: str
    ingest_error: str


def append_event(
    agent: str,
    decision: str,
    *,
    latency_ms: int = 0,
    tokens: int = 0,
    model: str = "mock",
    tool_calls: list[str] | None = None,
    error: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "timestamp": utcnow(),
        "agent": agent,
        "decision": decision,
        "latency_ms": latency_ms,
        "tokens": tokens,
        "model": model,
        "tool_calls": tool_calls or [],
        "error": error,
        "payload": payload or {},
    }
    metrics.record_event(event)
    return event
