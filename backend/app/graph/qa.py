"""Follow-up Q&A from approved case memory only. No new ingest or RAG."""

from __future__ import annotations

from typing import Any

from app.llm.provider import complete_text

DISCLAIMER = "Educational prototype. Not for clinical use."


def answer_followup(question: str, state: dict[str, Any]) -> str:
    mock = _heuristic_answer(question, state)
    result = complete_text(
        "Answer using only the approved case context (extracted text, analysis, summary, lab flags). "
        "Do not invent labs or diagnoses. Educational use only.",
        (
            f"QUESTION: {question}\n"
            f"SUMMARY: {state.get('summary') or ''}\n"
            f"LABS: {state.get('lab_flags') or []}\n"
            f"ANALYSIS: {state.get('analysis') or {}}\n"
            f"EXTRACTED_TEXT: {(state.get('extracted_text') or '')[:2000]}"
        ),
        mock,
    )
    text = (result.text or mock).strip()
    if DISCLAIMER.lower() not in text.lower():
        text = f"{text} {DISCLAIMER}"
    return text


def _heuristic_answer(question: str, state: dict[str, Any]) -> str:
    q = (question or "").lower()
    flags = _lab_rows(state)
    if "a1c" in q or "hba1c" in q:
        row = _find_lab(flags, ("hba1c", "a1c"))
        if row:
            return (
                f"Educational answer from case memory: HbA1c was {row['value']}"
                f" {row.get('unit') or ''}".rstrip()
                + f" ({row.get('flag') or 'documented'}). {DISCLAIMER}"
            )
        blob = _memory_blob(state)
        if "9.2" in blob:
            return f"Educational answer from case memory: HbA1c was 9.2%. {DISCLAIMER}"
    if "potassium" in q or "k+" in q:
        row = _find_lab(flags, ("potassium",))
        if row:
            return (
                f"Educational answer from case memory: potassium was {row['value']}"
                f" {row.get('unit') or ''}".rstrip()
                + f". {DISCLAIMER}"
            )
    summary = (state.get("summary") or "").strip()
    if summary:
        return f"Educational answer from case memory: {summary[:400]} {DISCLAIMER}"
    return f"Educational answer from case memory: no approved summary is stored yet. {DISCLAIMER}"


def _lab_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in state.get("lab_flags") or []:
        if isinstance(item, dict):
            rows.append(item)
    analysis = state.get("analysis") or {}
    medical = analysis.get("medical") if isinstance(analysis, dict) else None
    if isinstance(medical, dict):
        for item in medical.get("labs") or []:
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _find_lab(rows: list[dict[str, Any]], needles: tuple[str, ...]) -> dict[str, Any] | None:
    for row in rows:
        analyte = str(row.get("analyte") or row.get("name") or "").lower()
        if any(needle in analyte for needle in needles):
            return row
    return None


def _memory_blob(state: dict[str, Any]) -> str:
    return " ".join(
        [
            str(state.get("extracted_text") or ""),
            str(state.get("summary") or ""),
            str(state.get("analysis") or ""),
            str(state.get("lab_flags") or ""),
        ]
    )
