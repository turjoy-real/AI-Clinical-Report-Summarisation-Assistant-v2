"""Run / case persistence — Adarsh.

JSON-file records under backend/.runs/records/ plus an in-memory index. Thread-safe
via a re-entrant lock. No Postgres required. Owns run records only; the LangGraph
checkpointer stays Turjoy's.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT, get_settings
from app.contracts import ChatMessage, HumanDecision, Recommendation, RunEvent, RunRecord

_RECORDS_DIR = BACKEND_ROOT / ".runs" / "records"
_LOCK = threading.RLock()
_INDEX: dict[str, RunRecord] = {}
_LOADED = False

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _records_dir() -> Path:
    path = get_settings().runs_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(run_id: str) -> Path:
    return _records_dir() / f"{run_id}.json"


def new_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _SLUG_RE.sub("-", uuid.uuid4().hex[:8])
    return f"run-{stamp}-{slug}"


def _load_all() -> None:
    """Hydrate the in-memory index from disk once per process."""
    global _LOADED
    if _LOADED:
        return
    for file in _records_dir().glob("*.json"):
        try:
            record = RunRecord.model_validate(json.loads(file.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — tolerate corrupt/partial files on disk
            continue
        _INDEX[record.run_id] = record
    _LOADED = True


def _persist(record: RunRecord) -> None:
    _path(record.run_id).write_text(
        record.model_dump_json(indent=2),
        encoding="utf-8",
    )


def create_run(record: RunRecord) -> RunRecord:
    with _LOCK:
        _load_all()
        record.updated_at = record.updated_at or record.created_at
        _INDEX[record.run_id] = record
        _persist(record)
        return record.model_copy(deep=True)


def get_run(run_id: str) -> RunRecord | None:
    with _LOCK:
        _load_all()
        record = _INDEX.get(run_id)
        return record.model_copy(deep=True) if record else None


def list_runs() -> list[RunRecord]:
    with _LOCK:
        _load_all()
        records = sorted(_INDEX.values(), key=lambda r: r.created_at, reverse=True)
        return [r.model_copy(deep=True) for r in records]


def update_run(run_id: str, **fields: Any) -> RunRecord | None:
    """Patch top-level record fields (replaces lists/dicts wholesale) and persist."""
    with _LOCK:
        current = _INDEX.get(run_id)
        if current is None:
            return None
        data = current.model_dump()
        for key, value in fields.items():
            if key in {"run_id", "created_at"}:
                continue
            data[key] = value
        data["updated_at"] = _utcnow()
        updated = RunRecord.model_validate(data)
        _INDEX[run_id] = updated
        _persist(updated)
        return updated.model_copy(deep=True)


def append_events(run_id: str, events: list[RunEvent]) -> RunRecord | None:
    """Merge events that are not already stored (keyed on timestamp+agent+decision)."""
    if not events:
        return get_run(run_id)
    with _LOCK:
        current = _INDEX.get(run_id)
        if current is None:
            return None
        existing = {(e.timestamp, e.agent, e.decision) for e in current.events}
        fresh = [e for e in events if (e.timestamp, e.agent, e.decision) not in existing]
        if not fresh:
            return current.model_copy(deep=True)
        return update_run(run_id, events=[*(e.model_dump() for e in current.events), *(e.model_dump() for e in fresh)])


def record_decision(run_id: str, decision: HumanDecision) -> RunRecord | None:
    return update_run(run_id, human_decision=decision.model_dump())


def append_chat(run_id: str, message: ChatMessage) -> RunRecord | None:
    with _LOCK:
        current = _INDEX.get(run_id)
        if current is None:
            return None
        return update_run(run_id, chat_history=[*(m.model_dump() for m in current.chat_history), message.model_dump()])


def draft_to_recommendations(edits: str) -> list[Recommendation]:
    """Wrap clinician-edited text as a single recommendation entry."""
    text = (edits or "").strip()
    if not text:
        return []
    return [Recommendation(title="Clinician-edited plan", detail=text, citations=[])]


def _utcnow() -> str:
    from app.logging.observability import utcnow

    return utcnow()
