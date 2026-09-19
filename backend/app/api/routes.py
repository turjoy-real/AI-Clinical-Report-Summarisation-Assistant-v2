"""HTTP API — Adarsh.

Run store + SSE + HITL review wiring. The graph itself is Turjoy's; this module
calls it if present and falls back to a deterministic mock driver so the UI can
be developed before Phase 4.

Routes (team/CONTRACTS.md §7):
  GET  /api/health
  GET  /api/cases
  GET  /api/cases/{id}
  POST /api/runs
  GET  /api/runs
  GET  /api/runs/{id}
  GET  /api/runs/{id}/events      (SSE)
  POST /api/runs/{id}/review
  POST /api/runs/{id}/chat
  GET  /api/metrics               (stub zeros until Turjoy fills it)
  POST /api/rag/reindex           (Siva ingest → Vamsi embed; 501 if missing)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.contracts import (
    ChatMessage,
    ChatRequest,
    HumanDecision,
    Recommendation,
    ReviewRequest,
    RunEvent,
    RunRecord,
)
from app.logging.observability import metrics, utcnow
from app.memory import store

router = APIRouter(prefix="/api")

DISCLAIMER = "Educational prototype. Not for clinical use."
_TERMINAL_STATUSES = {"awaiting_review", "ingest_failed", "finalized"}

# Cases ------------------------------------------------------------------------


def _cases() -> list[dict[str, Any]]:
    path = Path(get_settings().data_dir) / "cases.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _read_report(relative: str | None) -> str:
    if not relative:
        return ""
    path = Path(get_settings().data_dir) / relative
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_labs(case: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(get_settings().data_dir) / (case.get("lab_path") or "")
    if not case.get("lab_path") or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for item in data.get("analytes", []):
        out.append(
            {
                "analyte": item.get("name", ""),
                "value": str(item.get("value", "")),
                "unit": item.get("unit", ""),
                "flag": "unknown",
            }
        )
    return out


@router.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "disclaimer": DISCLAIMER,
        "mock_llm": bool(settings.mock_llm),
        "live_llm": bool(settings.use_live_llm),
    }


@router.get("/cases")
def list_cases() -> list[dict[str, Any]]:
    return _cases()


@router.get("/cases/{case_id}")
def get_case(case_id: str) -> dict[str, Any]:
    for case in _cases():
        if case.get("case_id") == case_id:
            return {**case, "report_text": _read_report(case.get("report_path"))}
    raise HTTPException(status_code=404, detail=f"Unknown case {case_id}")


# Mock driver (used only when Turjoy's graph is not callable) --------------------


def _mock_draft(text: str) -> tuple[str, list[Recommendation]]:
    lowered = (text or "").lower()
    if "hba1c" in lowered or "diabetes" in lowered:
        topic = "diabetes"
        draft = (
            "SOAP-style draft (mock path): uncontrolled diabetes with HbA1c 9.2% on "
            "metformin monotherapy. Adherence and nutrition counseling discussed; "
            "therapy intensification deferred to the clinician. "
            "Educational prototype. Not for clinical use."
        )
        recs = [
            Recommendation(
                title="Discuss therapy intensification",
                detail="Teaching discussion of next-line options for HbA1c 9.2% on metformin.",
                citations=["Educational diabetes teaching card"],
            )
        ]
    elif "sepsis" in lowered or "lactate" in lowered:
        topic = "sepsis"
        draft = (
            "SOAP-style draft (mock path): suspected sepsis with lactate 4.2 mmol/L and "
            "hypotension documented. Urgent clinician review required. "
            "Educational prototype. Not for clinical use."
        )
        recs = [
            Recommendation(
                title="Confirm urgent escalation pathway",
                detail="Teaching discussion of sepsis bundle timing for the documented vitals.",
                citations=["Educational sepsis teaching card"],
            )
        ]
    else:
        topic = "general"
        draft = (
            "SOAP-style draft (mock path): no specific teaching topic matched; findings "
            "summarized from the pasted note only. Educational prototype. Not for clinical use."
        )
        recs = [
            Recommendation(
                title="Review findings with supervising clinician",
                detail="Draft is intentionally generic on the mock path.",
                citations=["Educational general teaching card"],
            )
        ]
    return topic, draft, recs


_MOCK_GRAPH_STATE: dict[str, dict[str, Any]] = {}


def _start_mock_run(record: RunRecord, text: str) -> None:
    """Deterministic driver: running → awaiting_review, then HITL transitions."""
    topic, draft, recs = _mock_draft(text)
    events = [
        RunEvent(timestamp=utcnow(), agent="router", decision=f"{topic}:routine", payload={"hitl_required": True}),
        RunEvent(timestamp=utcnow(), agent="fanout", decision="parallel_start"),
        RunEvent(timestamp=utcnow(), agent="analysis", decision="stub", payload={"source": "mock_driver"}),
        RunEvent(timestamp=utcnow(), agent="rag", decision="stub", payload={"source": "mock_driver"}),
        RunEvent(timestamp=utcnow(), agent="summary", decision="draft_ready"),
        RunEvent(timestamp=utcnow(), agent="safety", decision="draft_only", payload={"flags": ["hitl_locked"]}),
    ]
    _MOCK_GRAPH_STATE[record.run_id] = {"draft": draft, "recs": [r.model_dump() for r in recs]}
    store.update_run(
        record.run_id,
        status="awaiting_review",
        summary=draft,
        recommendations=[r.model_dump() for r in recs],
        citations=[{"title": r.citations[0]} for r in recs if r.citations],
        safety_flags=["hitl_locked"],
        events=[e.model_dump() for e in events],
    )


def _resume_mock_run(record: RunRecord, decision: str, edits: str) -> str:
    state = _MOCK_GRAPH_STATE.get(record.run_id)
    draft = (state or {}).get("draft") or record.summary
    if decision == "reject":
        revised = f"{draft}\n\n[Revision after clinician feedback: {edits or 'see comments'}]"
        if state:
            state["draft"] = revised
        store.update_run(
            record.run_id,
            status="awaiting_review",
            summary=revised,
            events=[RunEvent(timestamp=utcnow(), agent="hitl_review", decision="reject").model_dump()],
        )
        return "awaiting_review"
    if decision == "edit" and edits:
        recs = [{"title": "Clinician-edited plan", "detail": edits, "citations": []}]
    else:
        recs = [r.model_dump() for r in record.recommendations]
    store.update_run(
        record.run_id,
        status="finalized",
        summary=draft,
        recommendations=recs,
        events=[RunEvent(timestamp=utcnow(), agent="hitl_review", decision=decision).model_dump(),
                RunEvent(timestamp=utcnow(), agent="finalize", decision="released_after_hitl").model_dump()],
    )
    return "finalized"


# Graph driver (Turjoy) ---------------------------------------------------------


def _graph_runner():
    try:
        from app.graph.runs import start_run  # Turjoy's entry point if present
        return start_run
    except Exception:  # noqa: BLE001 — module or symbol may not exist yet
        return None


def _graph_resumer():
    try:
        from app.graph.runs import resume_after_review  # Turjoy's HITL resume if present
        return resume_after_review
    except Exception:  # noqa: BLE001
        return None


def _sync(coro_or_value: Any) -> Any:
    """Accept a coroutine or plain return from the graph layer."""
    if asyncio.iscoroutine(coro_or_value):
        return asyncio.run(coro_or_value)
    return coro_or_value


# Runs -------------------------------------------------------------------------


@router.post("/runs")
async def create_run(
    case_id: str | None = Form(default=None),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    pasted = (text or "").strip()
    filename = ""
    if file is not None and file.filename:
        filename = file.filename
        suffix = Path(filename).suffix.lower()
        raw = await file.read()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
                import io

                pasted = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
            except Exception:  # noqa: BLE001 — unreadable PDF → fail closed to pasted text
                pasted = ""
        elif suffix in {".md", ".txt", ".markdown", ""}:
            pasted = raw.decode("utf-8", errors="replace")
        else:
            raise HTTPException(status_code=415, detail="Unsupported file type. Use .md, .txt or .pdf")

    if not case_id and not pasted and not filename:
        raise HTTPException(status_code=422, detail="Provide a case_id, pasted text, or a file")

    now = utcnow()
    record = RunRecord(
        run_id=store.new_run_id(),
        case_id=case_id,
        status="running",
        source="library" if case_id else "upload",
        created_at=now,
        updated_at=now,
        events=[RunEvent(timestamp=now, agent="ingest", decision="run_created").model_dump()],
    )
    if case_id:
        try:
            case = get_case(case_id)
            record.lab_flags = _read_labs(case)
            pasted = pasted or case.get("report_text", "")
        except HTTPException:
            raise
    store.create_run(record)

    runner = _graph_runner()
    if runner is not None:
        try:
            result = _sync(runner(run_id=record.run_id, case_id=case_id, text=pasted, filename=filename))
            if isinstance(result, dict) and result.get("run_id"):
                return result
            if isinstance(result, str):
                return {"run_id": result, "status": store.get_run(result).status if store.get_run(result) else "running"}
        except Exception as exc:  # noqa: BLE001 — graph may not accept this signature yet
            store.update_run(record.run_id, status="ingest_failed", errors=[str(exc)])
            raise HTTPException(status_code=500, detail=f"start_run failed: {exc}") from exc

    # Fallback: drive the record so the UI can be developed before Phase 4.
    _start_mock_run(record, pasted)
    refreshed = store.get_run(record.run_id)
    return {"run_id": record.run_id, "status": refreshed.status if refreshed else "running"}


@router.get("/runs")
def list_runs() -> list[dict[str, Any]]:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    def _age_seconds(stamp: str) -> int | None:
        if not stamp:
            return None
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(0, int((now - parsed).total_seconds()))

    return [
        {
            "run_id": r.run_id,
            "case_id": r.case_id,
            "status": r.status,
            "urgency": r.urgency or (r.analysis or {}).get("urgency"),
            "specialty": r.specialty or (r.analysis or {}).get("specialty"),
            "source": r.source or ("library" if r.case_id else "upload"),
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "age_seconds": _age_seconds(r.created_at or r.updated_at),
        }
        for r in store.list_runs()
    ]


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    record = store.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run {run_id}")
    return record.model_dump()


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str) -> StreamingResponse:
    """SSE over the record's events list. Sends a snapshot, then follows changes."""
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown run {run_id}")

    async def generator() -> AsyncIterator[dict[str, str]]:
        sent = 0
        last_status = ""
        idle_ticks = 0
        while True:
            record = store.get_run(run_id)
            if record is None:
                break
            events = record.events
            for event in events[sent:]:
                sent += 1
                yield {"event": "agent", "data": json.dumps(event.model_dump())}
            if record.status != last_status:
                last_status = record.status
                yield {"event": "status", "data": json.dumps({"run_id": run_id, "status": record.status})}
            if record.status in _TERMINAL_STATUSES:
                idle_ticks += 1
                if idle_ticks > 20:  # ~1 min of keepalive after terminal status
                    yield {"event": "done", "data": json.dumps({"run_id": run_id, "status": record.status})}
                    break
            await asyncio.sleep(0.5)

    return EventSourceResponse(generator())


@router.post("/runs/{run_id}/review")
async def review_run(run_id: str, request: ReviewRequest) -> dict[str, Any]:
    record = store.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run {run_id}")
    if record.status not in {"awaiting_review", "revising"}:
        raise HTTPException(status_code=409, detail=f"Run is {record.status}; review needs awaiting_review")

    decided_at = utcnow()
    store.record_decision(
        run_id,
        HumanDecision(
            decision=request.decision,
            edits=request.edits,
            feedback=request.feedback,
            decided_at=decided_at,
        ),
    )
    store.append_events(
        run_id,
        [
            RunEvent(
                timestamp=decided_at,
                agent="clinician",
                decision=request.decision,
                payload={"edits": request.edits, "feedback": request.feedback},
            )
        ],
    )

    resumer = _graph_resumer()
    status: str | None = None
    if resumer is not None:
        try:
            outcome = _sync(resumer(run_id=run_id, decision=request.decision, edits=request.edits, feedback=request.feedback))
            status = outcome.get("status") if isinstance(outcome, dict) else outcome
        except Exception:  # noqa: BLE001 — fall back to record-only finalization
            status = None
    if status is None:
        status = _resume_mock_run(store.get_run(run_id) or record, request.decision, request.edits or request.feedback)

    refreshed = store.get_run(run_id)
    return {"run_id": run_id, "status": status or (refreshed.status if refreshed else record.status)}


@router.post("/runs/{run_id}/chat")
async def chat_run(run_id: str, request: ChatRequest) -> dict[str, Any]:
    record = store.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run {run_id}")
    if record.status != "finalized":
        raise HTTPException(status_code=409, detail="Available after approval")

    store.append_chat(run_id, ChatMessage(role="user", content=request.message, timestamp=utcnow()))
    from app.graph.qa import answer_followup

    analysis = record.analysis or {}
    answer = answer_followup(
        request.message,
        {
            "extracted_text": analysis.get("extracted_text") or record.summary,
            "analysis": analysis,
            "summary": record.summary,
            "lab_flags": [flag if isinstance(flag, dict) else flag.model_dump() for flag in record.lab_flags],
        },
    )

    store.append_chat(run_id, ChatMessage(role="assistant", content=answer, timestamp=utcnow()))
    refreshed = store.get_run(run_id)
    return {"reply": answer, "chat_history": [m.model_dump() for m in (refreshed.chat_history if refreshed else [])]}


# Metrics + RAG ----------------------------------------------------------------


@router.get("/metrics")
def get_metrics() -> dict[str, Any]:
    snap = metrics.snapshot()
    runs = store.list_runs()
    hitl_from_store = {
        "approve": sum(1 for r in runs if (r.human_decision.decision or "pending") == "approve"),
        "edit": sum(1 for r in runs if (r.human_decision.decision or "pending") == "edit"),
        "reject": sum(1 for r in runs if (r.human_decision.decision or "pending") == "reject"),
    }
    snap["runs_total"] = max(int(snap.get("runs_total") or 0), len(runs))
    snap["runs_finalized"] = sum(1 for r in runs if r.status == "finalized")
    if not snap.get("hitl_approvals"):
        snap["hitl_approvals"] = hitl_from_store["approve"]
        snap["hitl_rejections"] = hitl_from_store["reject"]
        snap["hitl_mix"] = {**hitl_from_store, **(snap.get("hitl_mix") or {})}
    return snap


@router.post("/rag/reindex")
async def rag_reindex() -> dict[str, Any]:
    settings = get_settings()
    guidelines_dir = str(Path(settings.data_dir) / "guidelines")
    try:
        from app.rag.ingest import ingest_guideline_corpus

        chunks = ingest_guideline_corpus(guidelines_dir)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=501, detail=f"ingest_guideline_corpus not available: {exc}") from exc
    try:
        from app.rag.retrieve import embed_guidelines

        embedded = embed_guidelines()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=501, detail=f"embed_guidelines not available: {exc}") from exc
    return {"disclaimer": DISCLAIMER, "chunks": chunks, "embedded": embedded}
