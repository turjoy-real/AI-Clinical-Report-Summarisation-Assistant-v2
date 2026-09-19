"""Patient-demographics extraction owned by Radhakrishna."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from app.config import get_settings
from app.contracts import PatientData
from app.extract.patient_heuristics import extract_patient_heuristics
from app.extract.patient_prompt import PATIENT_SYSTEM_PROMPT


_PATIENT_FIELDS = ("name", "age", "sex", "mrn", "setting", "date")


def _extract_with_gemini(document_text: str) -> PatientData:
    """Use LangChain's Gemini integration, raising so the caller can fall back."""
    settings = get_settings()
    from langchain_google_genai import ChatGoogleGenerativeAI

    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        timeout=20,
    )
    response = model.invoke([("system", PATIENT_SYSTEM_PROMPT), ("human", document_text)])
    content = response.content if isinstance(response.content, str) else json.dumps(response.content)
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("Gemini did not return a JSON object")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Gemini JSON was not an object")
    cleaned = {key: payload.get(key) for key in _PATIENT_FIELDS if payload.get(key) is not None}
    if "age" in cleaned:
        cleaned["age"] = int(cleaned["age"])
    return PatientData(**cleaned)


def extract_patient_data(document_text: str) -> PatientData:
    """Return demographics only, using Gemini when configured or local heuristics."""
    text = document_text or ""
    if not text.strip():
        return PatientData()
    settings = get_settings()
    if not settings.mock_llm and settings.has_gemini:
        try:
            patient = _extract_with_gemini(text)
            case_id = extract_patient_heuristics(text).source_case_id
            return patient.model_copy(update={"source_case_id": case_id})
        except Exception:
            pass
    return extract_patient_heuristics(text)


def _main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.extract.patient <report-path>")
    path = Path(sys.argv[1])
    if not path.exists():
        path = Path(__file__).resolve().parents[3] / sys.argv[1]
    try:
        patient = extract_patient_data(path.read_text(encoding="utf-8"))
    except OSError:
        patient = PatientData()
    print("PATIENT " + patient.model_dump_json())


if __name__ == "__main__":
    _main()
