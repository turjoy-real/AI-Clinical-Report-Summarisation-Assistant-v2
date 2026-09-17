"""Medical data extraction. Owned by Vinayak.

Uses LangChain + Gemini for structured extraction of clinical content only
(chief concern, problems, medications, allergies, vitals, labs, assessment,
plan). Demographics (name, age, sex, MRN) are Radhakrishna's responsibility
and must never appear here.

Env behavior:
- MOCK_LLM=true            -> never call Gemini, use heuristics only.
- MOCK_LLM=false + key set -> call Gemini via LangChain.
- On timeout/error         -> fall back to heuristics.
"""

from __future__ import annotations

import json
import logging
import re

from app.contracts import LabFlag, MedicalData
from app.extract.medical_heuristics import extract_medical_heuristic
from app.extract.medical_prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

_VALID_FLAGS = {"normal", "high", "low", "critical_high", "critical_low", "unknown"}


def _get_settings():
    from app.config import get_settings

    return get_settings()


def _coerce_medical_data(payload: dict) -> MedicalData:
    labs_raw = payload.get("labs") or []
    labs: list[LabFlag] = []
    for item in labs_raw:
        if not isinstance(item, dict):
            continue
        flag = item.get("flag", "unknown")
        if flag not in _VALID_FLAGS:
            flag = "unknown"
        labs.append(
            LabFlag(
                analyte=str(item.get("analyte", "")).strip(),
                value=str(item.get("value", "")).strip(),
                unit=str(item.get("unit", "") or ""),
                flag=flag,
            )
        )

    vitals_raw = payload.get("vitals") or {}
    vitals = {str(k): str(v) for k, v in vitals_raw.items()} if isinstance(vitals_raw, dict) else {}

    def _str_list(key: str) -> list[str]:
        value = payload.get(key) or []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return []

    return MedicalData(
        chief_concern=str(payload.get("chief_concern", "") or ""),
        problems=_str_list("problems"),
        medications=_str_list("medications"),
        allergies=_str_list("allergies"),
        vitals=vitals,
        labs=labs,
        assessment=str(payload.get("assessment", "") or ""),
        plan=str(payload.get("plan", "") or ""),
        missing_sections=_str_list("missing_sections"),
    )


def _parse_json_response(raw_text: str) -> dict | None:
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    # Strip markdown fences if the model added them despite instructions.
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _gemini_extract(document_text: str) -> MedicalData | None:
    """Call Gemini through LangChain. Returns None on any failure."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        logger.warning("langchain-google-genai not installed; falling back to heuristics")
        return None

    settings = _get_settings()
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
            timeout=20,
        )
        response = llm.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=build_user_prompt(document_text)),
            ]
        )
        text = response.content if isinstance(response.content, str) else str(response.content)
        payload = _parse_json_response(text)
        if payload is None:
            logger.warning("Gemini medical extraction returned non-JSON output; falling back")
            return None
        return _coerce_medical_data(payload)
    except Exception as exc:  # noqa: BLE001 - any provider/timeout error triggers fallback
        logger.warning("Gemini medical extraction failed (%s); falling back to heuristics", exc)
        return None


def extract_medical_data(document_text: str) -> MedicalData:
    """Clinical content only. No name, age, MRN, or sex."""
    text = document_text or ""
    if not text.strip():
        return MedicalData()

    settings = _get_settings()

    if settings.mock_llm or not settings.has_gemini:
        return extract_medical_heuristic(text)

    result = _gemini_extract(text)
    if result is not None:
        return result

    return extract_medical_heuristic(text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m app.extract.medical <path-to-note>")
        raise SystemExit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        note_text = fh.read()

    data = extract_medical_data(note_text)
    print(json.dumps({"MEDICAL": data.model_dump()}, indent=2))
