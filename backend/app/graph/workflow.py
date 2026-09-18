from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.contracts import MedicalData, PatientData, Recommendation, RetrievedDoc
from app.extract.medical import extract_medical_data
from app.extract.patient import extract_patient_data
from app.graph.router import refine_route
from app.graph.safety import lock_hitl, safety_flags_from_state
from app.graph.state import GraphState, append_event
from app.rag.ingest import ingest_guideline_corpus, list_guideline_chunks
from app.rag.retrieve import retrieve_guidelines
from app.summarize.recommend import create_recommendations
from app.summarize.summary import create_indepth_summary
from app.tools.pdf import PdfExtractError, extract_pdf_text

RECOVERY_COPY = "Paste the note as text."


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
    started = time.perf_counter()
    raw = state.get("raw_text") or ""
    source = state.get("report_type") or ""
    text = raw
    tools: list[str] = []
    error = None
    source_path = Path(str(source)) if source else None
    if source_path and source_path.suffix.lower() == ".pdf" and source_path.is_file():
        tools.append("extract_pdf_text")
        try:
            text = extract_pdf_text(source_path)
        except PdfExtractError as exc:
            error = str(exc) or RECOVERY_COPY
            text = raw
        except Exception as exc:  # noqa: BLE001 — fail closed
            error = f"{RECOVERY_COPY} ({exc})"
            text = raw
    if not error and _looks_garbled(text):
        error = RECOVERY_COPY
    latency = int((time.perf_counter() - started) * 1000)
    if error:
        return {
            "extracted_text": text,
            "ingest_error": error,
            "status": "ingest_failed",
            "errors": [error],
            "events": [
                append_event("ingest", "ingest_failed", latency_ms=latency, tool_calls=tools, error=error)
            ],
        }
    return {
        "extracted_text": text,
        "status": "ingested",
        "errors": [],
        "events": [
            append_event(
                "ingest",
                "text_normalized",
                latency_ms=latency,
                tool_calls=tools,
                payload={"chars": len(text)},
            )
        ],
    }


def router_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    parsed = refine_route(state.get("extracted_text") or "")
    hitl_required = parsed["urgency"] == "critical"
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "specialty": parsed["specialty"],
        "urgency": parsed["urgency"],
        "router_confidence": parsed.get("router_confidence", 0.0),
        "router_rationale": parsed.get("router_rationale", ""),
        "model_used": parsed.get("model_used", "mock"),
        "hitl_required": hitl_required,
        "status": "routed",
        "errors": [],
        "events": [
            append_event(
                "router",
                f"{parsed['specialty']}:{parsed['urgency']}",
                latency_ms=latency,
                model=str(parsed.get("model_used") or "mock"),
                payload={"hitl_required": hitl_required, **parsed},
            )
        ],
    }


def urgent_safety_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    flags = lock_hitl("critical", safety_flags_from_state(state.get("extracted_text") or "", state.get("lab_flags")))
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "safety_flags": flags,
        "hitl_required": True,
        "errors": [],
        "events": [
            append_event(
                "urgent_safety",
                "critical_gate",
                latency_ms=latency,
                payload={"flags": flags, "lock_hitl": True},
            )
        ],
    }


def fanout_node(state: GraphState) -> dict[str, Any]:
    return {
        "errors": [],
        "events": [append_event("fanout", "parallel_start", payload={"urgency": state.get("urgency")})],
    }


def analysis_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    text = state.get("extracted_text") or ""
    patient = extract_patient_data(text)
    medical = extract_medical_data(text)
    analysis = {
        "patient": patient.model_dump(),
        "medical": medical.model_dump(),
        "extracted_text": text,
        "specialty": state.get("specialty"),
        "urgency": state.get("urgency"),
    }
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "analysis": analysis,
        "errors": [],
        "events": [
            append_event(
                "analysis",
                "entities_extracted",
                latency_ms=latency,
                tool_calls=["extract_patient_data", "extract_medical_data"],
                payload={"problems": medical.problems, "name": patient.name},
            )
        ],
    }


def labs_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    medical = extract_medical_data(state.get("extracted_text") or "")
    lab_flags = [lab.model_dump() for lab in medical.labs]
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "lab_flags": lab_flags,
        "errors": [],
        "events": [
            append_event(
                "labs",
                "labs_flagged",
                latency_ms=latency,
                tool_calls=["extract_medical_data"],
                payload={"count": len(lab_flags)},
            )
        ],
    }


def rag_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    text = state.get("extracted_text") or ""
    specialty = state.get("specialty")
    if not list_guideline_chunks():
        ingest_guideline_corpus(str(get_settings().data_dir / "guidelines"))
    query = text[:800]
    docs = retrieve_guidelines(query, specialty=specialty, k=4)
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "retrieved_docs": [doc.model_dump() for doc in docs],
        "errors": [],
        "events": [
            append_event(
                "rag",
                "guidelines_retrieved" if docs else "no_guideline_match",
                latency_ms=latency,
                tool_calls=["retrieve_guidelines"],
                payload={"topics": [doc.topic for doc in docs], "doc_ids": [doc.id for doc in docs]},
            )
        ],
    }


def synthesize_node(state: GraphState) -> dict[str, Any]:
    return {
        "errors": [],
        "events": [
            append_event(
                "synthesize",
                "parallel_join",
                payload={
                    "has_analysis": bool(state.get("analysis")),
                    "lab_flags": len(state.get("lab_flags") or []),
                    "docs": len(state.get("retrieved_docs") or []),
                },
            )
        ],
    }


def _patient_medical_docs(state: GraphState) -> tuple[PatientData, MedicalData, list[RetrievedDoc]]:
    analysis = state.get("analysis") or {}
    patient_raw = analysis.get("patient") if isinstance(analysis, dict) else None
    medical_raw = analysis.get("medical") if isinstance(analysis, dict) else None
    patient = PatientData.model_validate(patient_raw or {})
    medical = MedicalData.model_validate(medical_raw or {})
    docs: list[RetrievedDoc] = []
    for item in state.get("retrieved_docs") or []:
        try:
            docs.append(RetrievedDoc.model_validate(item))
        except Exception:
            continue
    return patient, medical, docs


def summary_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    patient, medical, docs = _patient_medical_docs(state)
    draft = create_indepth_summary(patient, medical, docs)
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "summary": draft.summary,
        "used_topics": draft.used_topics,
        "errors": [],
        "events": [
            append_event(
                "summary",
                "summary_drafted",
                latency_ms=latency,
                payload={"used_topics": draft.used_topics},
            )
        ],
    }


def recommendation_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    patient, medical, docs = _patient_medical_docs(state)
    recs = create_recommendations(patient, medical, docs)
    dumped = [rec.model_dump() for rec in recs]
    citations = [{"title": cite} for rec in recs for cite in rec.citations]
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "recommendations": dumped,
        "citations": citations,
        "status": "awaiting_review",
        "errors": [],
        "events": [
            append_event(
                "recommendation",
                "recommendations_drafted",
                latency_ms=latency,
                payload={"count": len(dumped)},
            )
        ],
    }


def safety_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    flags = safety_flags_from_state(state.get("extracted_text") or "", state.get("lab_flags"))
    flags = lock_hitl(state.get("urgency"), flags)
    hitl_required = True if state.get("urgency") == "critical" else bool(state.get("hitl_required") or flags)
    if state.get("urgency") == "critical":
        hitl_required = True
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "safety_flags": flags,
        "hitl_required": hitl_required or True,  # drafts always pause for clinician review
        "status": "awaiting_review",
        "errors": [],
        "events": [
            append_event(
                "safety",
                "draft_only",
                latency_ms=latency,
                payload={"flags": flags, "lock_hitl": True},
            )
        ],
    }


def hitl_review_node(state: GraphState) -> dict[str, Any]:
    decision = state.get("human_decision") or "pending"
    if decision == "reject":
        return {
            "status": "revising",
            "errors": [],
            "events": [
                append_event("hitl_review", "rejected", payload={"feedback": state.get("human_feedback")})
            ],
        }
    if decision == "edit":
        recs = list(state.get("recommendations") or [])
        if state.get("human_edits"):
            citations = recs[0].get("citations") if recs else []
            recs = [
                {
                    "title": "Clinician-edited recommendations",
                    "detail": state["human_edits"],
                    "citations": citations or [],
                }
            ]
        return {
            "recommendations": recs,
            "status": "approved_with_edits",
            "errors": [],
            "events": [append_event("hitl_review", "edited")],
        }
    return {
        "status": "approved",
        "errors": [],
        "events": [append_event("hitl_review", "approved")],
    }


def revise_node(state: GraphState) -> dict[str, Any]:
    started = time.perf_counter()
    feedback = state.get("human_feedback") or "Clinician rejected the draft; produce a more conservative revision."
    patient, medical, docs = _patient_medical_docs(state)
    draft = create_indepth_summary(patient, medical, docs)
    recs = create_recommendations(patient, medical, docs)
    dumped = [rec.model_dump() for rec in recs]
    dumped.insert(
        0,
        Recommendation(
            title="Revised after clinician feedback",
            detail=(
                "Educational prototype. Not for clinical use. Conservative revision: discuss findings "
                f"with a clinician. Feedback considered: {feedback}"
            ),
            citations=[doc.citation or doc.title for doc in docs[:1] if doc.citation or doc.title],
        ).model_dump(),
    )
    citations = [{"title": cite} for rec in dumped for cite in rec.get("citations") or []]
    summary = (
        f"{draft.summary}\n\n## Revision note\n"
        f"Conservative revision after clinician feedback. {feedback}"
    )
    latency = int((time.perf_counter() - started) * 1000)
    return {
        "summary": summary,
        "recommendations": dumped,
        "citations": citations,
        "human_decision": "pending",
        "status": "revising",
        "errors": [],
        "events": [
            append_event("revise", "revised_from_feedback", latency_ms=latency, payload={"feedback": feedback})
        ],
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


def after_hitl(state: GraphState) -> Literal["revise", "finalize"]:
    return "revise" if state.get("status") == "revising" else "finalize"


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
    builder.add_node("revise", revise_node)
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
    builder.add_conditional_edges("hitl_review", after_hitl, {"revise": "revise", "finalize": "finalize"})
    builder.add_edge("revise", "safety")
    builder.add_edge("finalize", END)

    return builder.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_before=["hitl_review"],
    )


@lru_cache
def get_graph():
    return build_graph()
