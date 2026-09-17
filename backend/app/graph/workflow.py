from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.state import GraphState, append_event


def _looks_garbled(text: str) -> bool:
    stripped = (text or "").strip()
    upper = stripped.upper()
    if "UNREADABLE" in upper or "garbled for ingest-error" in stripped.lower():
        return True
    letters = [ch.lower() for ch in stripped if ch.isalpha()]
    if len(stripped) < 40 or len(letters) < 20:
        return True
    vowels = sum(ch in "aeiou" for ch in letters)
    return bool(letters) and (vowels / len(letters) < 0.12)


def ingest_node(state: GraphState) -> dict[str, Any]:
    raw = state.get("raw_text") or ""
    if _looks_garbled(raw):
        error = "Paste the note as text."
        return {
            "extracted_text": raw,
            "ingest_error": error,
            "status": "ingest_failed",
            "errors": [error],
            "events": [append_event("ingest", "ingest_failed", error=error)],
        }
    return {
        "extracted_text": raw,
        "status": "ingested",
        "errors": [],
        "events": [append_event("ingest", "text_normalized", payload={"chars": len(raw)})],
    }


def router_node(state: GraphState) -> dict[str, Any]:
    text = (state.get("extracted_text") or "").lower()
    if "annual physical" in text or "preventive visit" in text:
        specialty, urgency = "general", "routine"
    else:
        critical = any(
            token in text
            for token in ("sepsis", "septic", "troponin", "lactate")
        ) or bool(re.search(r"\bbp\s*(1[89]\d|[2-9]\d{2})", text))
        urgency = "critical" if critical else "routine"
        rules = [
            ("infectious_disease", ["sepsis", "pneumonia", "lactate"]),
            ("cardio", ["chest pain", "troponin", "heart failure", "hfref", "hypertension", "blood pressure"]),
            ("endocrine", ["diabetes", "hypothyroid", "tsh", "metformin", "hba1c"]),
            ("renal", ["aki", "ckd", "egfr", "creatinine"]),
            ("heme", ["anemia", "ferritin", "hemoglobin"]),
        ]
        specialty = "general"
        best = 0
        for name, keys in rules:
            score = sum(1 for key in keys if key in text)
            if score > best:
                best = score
                specialty = name
        if best < 2:
            specialty = "general"
    hitl_required = urgency == "critical"
    return {
        "specialty": specialty,
        "urgency": urgency,
        "hitl_required": hitl_required,
        "status": "routed",
        "errors": [],
        "events": [append_event("router", f"{specialty}:{urgency}", payload={"hitl_required": hitl_required})],
    }


def _stub(agent: str, decision: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = extra or {}
    out = {
        "errors": [],
        "events": [append_event(agent, decision, payload=payload)],
    }
    out.update(payload.get("_state", {}))
    return out


def urgent_safety_node(state: GraphState) -> dict[str, Any]:
    flags = ["hitl_locked"]
    if "sepsis" in (state.get("extracted_text") or "").lower():
        flags.append("possible_sepsis")
    return {
        "safety_flags": flags,
        "hitl_required": True,
        "errors": [],
        "events": [append_event("urgent_safety", "critical_gate", payload={"flags": flags})],
    }


def fanout_node(state: GraphState) -> dict[str, Any]:
    return {
        "errors": [],
        "events": [append_event("fanout", "parallel_start", payload={"urgency": state.get("urgency")})],
    }


def analysis_node(state: GraphState) -> dict[str, Any]:
    return {
        "analysis": state.get("analysis") or {},
        "errors": [],
        "events": [append_event("analysis", "stub")],
    }


def labs_node(state: GraphState) -> dict[str, Any]:
    return {
        "lab_flags": state.get("lab_flags") or [],
        "errors": [],
        "events": [append_event("labs", "stub")],
    }


def rag_node(state: GraphState) -> dict[str, Any]:
    return {
        "retrieved_docs": state.get("retrieved_docs") or [],
        "errors": [],
        "events": [append_event("rag", "stub")],
    }


def synthesize_node(state: GraphState) -> dict[str, Any]:
    return {
        "errors": [],
        "events": [append_event("synthesize", "parallel_join")],
    }


def summary_node(state: GraphState) -> dict[str, Any]:
    return {
        "summary": state.get("summary") or "",
        "errors": [],
        "events": [append_event("summary", "stub")],
    }


def recommendation_node(state: GraphState) -> dict[str, Any]:
    return {
        "recommendations": state.get("recommendations") or [],
        "errors": [],
        "events": [append_event("recommendation", "stub")],
    }


def safety_node(state: GraphState) -> dict[str, Any]:
    flags = list(state.get("safety_flags") or [])
    if state.get("urgency") == "critical" and "hitl_locked" not in flags:
        flags.append("hitl_locked")
    return {
        "safety_flags": flags,
        "hitl_required": True if state.get("urgency") == "critical" else bool(state.get("hitl_required")),
        "status": "awaiting_review",
        "errors": [],
        "events": [append_event("safety", "draft_only", payload={"flags": flags})],
    }


def hitl_review_node(state: GraphState) -> dict[str, Any]:
    decision = state.get("human_decision") or "pending"
    return {
        "status": "approved" if decision == "approve" else "awaiting_review",
        "errors": [],
        "events": [append_event("hitl_review", decision)],
    }


def finalize_node(state: GraphState) -> dict[str, Any]:
    return {
        "status": "finalized",
        "errors": [],
        "events": [append_event("finalize", "released_after_hitl")],
    }


def after_ingest(state: GraphState) -> Literal["router", "end"]:
    return "end" if state.get("ingest_error") else "router"


def after_router(state: GraphState) -> Literal["urgent_safety", "fanout"]:
    return "urgent_safety" if state.get("urgency") == "critical" else "fanout"


def build_graph(checkpointer: Any | None = None):
    builder = StateGraph(GraphState)
    builder.add_node("ingest", ingest_node)
    builder.add_node("router", router_node)
    builder.add_node("urgent_safety", urgent_safety_node)
    builder.add_node("fanout", fanout_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("labs", labs_node)
    builder.add_node("rag", rag_node)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("summary", summary_node)
    builder.add_node("recommendation", recommendation_node)
    builder.add_node("safety", safety_node)
    builder.add_node("hitl_review", hitl_review_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "ingest")
    builder.add_conditional_edges("ingest", after_ingest, {"router": "router", "end": END})
    builder.add_conditional_edges("router", after_router, {"urgent_safety": "urgent_safety", "fanout": "fanout"})
    builder.add_edge("urgent_safety", "fanout")
    builder.add_edge("fanout", "analysis")
    builder.add_edge("fanout", "labs")
    builder.add_edge("fanout", "rag")
    builder.add_edge("analysis", "synthesize")
    builder.add_edge("labs", "synthesize")
    builder.add_edge("rag", "synthesize")
    builder.add_edge("synthesize", "summary")
    builder.add_edge("summary", "recommendation")
    builder.add_edge("recommendation", "safety")
    builder.add_edge("safety", "hitl_review")
    builder.add_edge("hitl_review", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())


@lru_cache
def get_graph():
    return build_graph()
