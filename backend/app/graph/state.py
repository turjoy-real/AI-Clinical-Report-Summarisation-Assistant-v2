from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.logging.observability import utcnow


class GraphState(TypedDict, total=False):
    thread_id: str
    case_id: str
    raw_text: str
    extracted_text: str
    specialty: str
    urgency: str
    analysis: dict[str, Any]
    lab_flags: list[dict[str, Any]]
    retrieved_docs: list[dict[str, Any]]
    summary: str
    recommendations: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    safety_flags: list[str]
    hitl_required: bool
    human_decision: str
    human_edits: str
    human_feedback: str
    chat_history: list[dict[str, str]]
    errors: Annotated[list[str], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
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
    return {
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
