"""Run lifecycle Adarsh's API calls: start, inspect, resume HITL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.contracts import RunEvent, RunRecord
from app.graph.workflow import get_graph
from app.logging.observability import metrics, utcnow
from app.memory import store


def _drafts_dir() -> Path:
    from app.config import get_settings

    path = get_settings().log_dir / "graph_drafts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _draft_path(run_id: str) -> Path:
    return _drafts_dir() / f"{run_id}.json"


def _save_draft(run_id: str, values: dict[str, Any]) -> None:
    payload = {
        "summary": values.get("summary") or "",
        "recommendations": values.get("recommendations") or [],
        "citations": values.get("citations") or [],
        "lab_flags": values.get("lab_flags") or [],
        "retrieved_docs": values.get("retrieved_docs") or [],
        "safety_flags": values.get("safety_flags") or [],
        "analysis": values.get("analysis") or {},
        "extracted_text": values.get("extracted_text") or "",
        "status": values.get("status") or "",
        "specialty": values.get("specialty"),
        "urgency": values.get("urgency"),
        "events": values.get("events") or [],
        "errors": values.get("errors") or [],
        "ingest_error": values.get("ingest_error") or "",
    }
    _draft_path(run_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_draft(run_id: str) -> dict[str, Any] | None:
    path = _draft_path(run_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_jsonl(run_id: str, events: list[dict[str, Any]]) -> None:
    from app.config import get_settings

    path = get_settings().log_dir / f"{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            if isinstance(event, dict):
                handle.write(json.dumps(event) + "\n")


def _persist_to_store(run_id: str, values: dict[str, Any]) -> None:
    events = values.get("events") or []
    analysis = dict(values.get("analysis") or {})
    if values.get("extracted_text") and "extracted_text" not in analysis:
        analysis["extracted_text"] = values.get("extracted_text")
    record = store.get_run(run_id)
    source = "library" if (record and record.case_id) or values.get("case_id") else "upload"
    store.update_run(
        run_id,
        status=values.get("status") or "running",
        summary=values.get("summary") or "",
        extracted_text=values.get("extracted_text") or analysis.get("extracted_text") or "",
        specialty=values.get("specialty"),
        urgency=values.get("urgency"),
        source=source,
        recommendations=values.get("recommendations") or [],
        citations=values.get("citations") or [],
        lab_flags=values.get("lab_flags") or [],
        retrieved_docs=values.get("retrieved_docs") or [],
        safety_flags=values.get("safety_flags") or [],
        analysis=analysis,
        errors=values.get("errors") or [],
        events=events,
    )
    _write_jsonl(run_id, events)
    _save_draft(run_id, values)


def _initial_state(run_id: str, text: str, case_id: str | None, filename: str) -> dict[str, Any]:
    return {
        "thread_id": run_id,
        "case_id": case_id or "",
        "raw_text": text or "",
        "extracted_text": "",
        "report_type": filename or "text",
        "human_decision": "pending",
        "errors": [],
        "events": [],
        "status": "running",
    }


def _ensure_record(run_id: str, case_id: str | None) -> None:
    if store.get_run(run_id) is not None:
        return
    now = utcnow()
    store.create_run(
        RunRecord(run_id=run_id, case_id=case_id, status="running", created_at=now, updated_at=now)
    )


def start_run(
    text: str = "",
    case_id: str | None = None,
    *,
    run_id: str | None = None,
    filename: str = "",
) -> dict[str, Any]:
    """Invoke the graph until HITL interrupt (or ingest failure)."""
    run_id = run_id or store.new_run_id()
    _ensure_record(run_id, case_id)
    graph = get_graph()
    config = {"configurable": {"thread_id": run_id}}
    graph.invoke(_initial_state(run_id, text, case_id, filename), config)
    snapshot = graph.get_state(config)
    values = dict(snapshot.values or {})
    if snapshot.next == ("hitl_review",):
        values["status"] = "awaiting_review"
    _persist_to_store(run_id, values)
    metrics.record_run(values.get("urgency"), values.get("specialty"), values.get("model_used") or "mock")
    return {"run_id": run_id, "status": values.get("status") or "running"}


def get_state(run_id: str) -> dict[str, Any]:
    graph = get_graph()
    snapshot = graph.get_state({"configurable": {"thread_id": run_id}})
    values = dict(snapshot.values or {})
    if not values:
        draft = _load_draft(run_id)
        if draft:
            return draft
        record = store.get_run(run_id)
        return record.model_dump() if record else {}
    values["next"] = list(snapshot.next or [])
    return values


def apply_review(run_id: str, decision: str, edits: str = "", feedback: str = "") -> dict[str, Any]:
    graph = get_graph()
    config = {"configurable": {"thread_id": run_id}}
    snapshot = graph.get_state(config)
    resumable = bool(snapshot.values) and snapshot.next == ("hitl_review",)
    if not resumable:
        return _fallback_review(run_id, decision, edits, feedback)

    graph.update_state(
        config,
        {
            "human_decision": decision,
            "human_edits": edits or "",
            "human_feedback": feedback or "",
        },
    )
    graph.invoke(None, config)
    snapshot = graph.get_state(config)
    values = dict(snapshot.values or {})
    if snapshot.next == ("hitl_review",):
        values["status"] = "awaiting_review"
    _persist_to_store(run_id, values)
    metrics.record_hitl(decision)
    return {"run_id": run_id, "status": values.get("status") or "running"}


def resume_after_review(
    run_id: str,
    decision: str,
    edits: str = "",
    feedback: str = "",
) -> dict[str, Any]:
    return apply_review(run_id, decision, edits=edits, feedback=feedback)


def _fallback_review(run_id: str, decision: str, edits: str, feedback: str) -> dict[str, Any]:
    """If the LangGraph checkpoint is gone, finalize (or re-draft) from the saved JSON."""
    record = store.get_run(run_id)
    draft = _load_draft(run_id) or (record.model_dump() if record else {})
    if not draft:
        return {"run_id": run_id, "status": "ingest_failed"}

    events = list(draft.get("events") or [])
    if decision == "reject":
        summary = (draft.get("summary") or "") + (
            f"\n\n## Revision note\nConservative revision after clinician feedback. {feedback or 'see comments'}"
        )
        recs = list(draft.get("recommendations") or [])
        recs.insert(
            0,
            {
                "title": "Revised after clinician feedback",
                "detail": (
                    "Educational prototype. Not for clinical use. Conservative revision: discuss findings "
                    f"with a clinician. Feedback considered: {feedback or 'see comments'}"
                ),
                "citations": [],
            },
        )
        events.append(RunEvent(timestamp=utcnow(), agent="hitl_review", decision="rejected").model_dump())
        values = {
            **draft,
            "summary": summary,
            "recommendations": recs,
            "status": "awaiting_review",
            "events": events,
        }
        _persist_to_store(run_id, values)
        metrics.record_hitl(decision)
        return {"run_id": run_id, "status": "awaiting_review"}

    recs = list(draft.get("recommendations") or [])
    if decision == "edit" and edits:
        citations = recs[0].get("citations") if recs else []
        recs = [{"title": "Clinician-edited recommendations", "detail": edits, "citations": citations or []}]
    events.append(RunEvent(timestamp=utcnow(), agent="hitl_review", decision=decision).model_dump())
    events.append(RunEvent(timestamp=utcnow(), agent="finalize", decision="released_after_hitl").model_dump())
    values = {**draft, "recommendations": recs, "status": "finalized", "events": events}
    _persist_to_store(run_id, values)
    metrics.record_hitl(decision)
    return {"run_id": run_id, "status": "finalized"}
