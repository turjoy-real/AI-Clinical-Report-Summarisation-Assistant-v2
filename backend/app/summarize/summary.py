"""In-depth SOAP summary generation. Owned by Sneha.

Uses LangChain + Gemini for a grounded, in-depth educational SOAP writeup
built strictly from patient_data, medical_data, and retrieved_docs. Never
calls extract_* or retrieve_guidelines itself, and never emits a
recommendations list (that is Lakshmi's create_recommendations).

Env behavior:
- MOCK_LLM=true            -> never call Gemini, use heuristics only.
- MOCK_LLM=false + key set -> call Gemini via LangChain.
- On timeout/error/bad JSON -> fall back to heuristics.
"""

from __future__ import annotations

import json
import logging
import re

from app.contracts import MedicalData, PatientData, RetrievedDoc, SummaryDraft
from app.extract.medical_heuristics import _MEDICATIONS
from app.summarize.summary_heuristics import DISCLAIMER, build_indepth_summary_heuristic
from app.summarize.summary_prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


def _get_settings():
    from app.config import get_settings

    return get_settings()


def _parse_json_response(raw_text: str) -> dict | None:
    if not raw_text:
        return None
    cleaned = raw_text.strip()
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


def _strip_uninvented_medications(summary: str, medical_data: MedicalData) -> str:
    """Drop any sentence naming a known drug that is not in medical_data.medications."""
    allowed = {med.lower() for med in medical_data.medications}
    unlisted = [med for med in _MEDICATIONS if med not in allowed]
    if not unlisted:
        return summary

    def _clean_paragraph(paragraph: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        kept = [s for s in sentences if not any(med in s.lower() for med in unlisted)]
        return " ".join(kept).strip()

    paragraphs = summary.split("\n\n")
    cleaned = [_clean_paragraph(p) if not p.startswith("##") else p for p in paragraphs]
    return "\n\n".join(p for p in cleaned if p)


def _coerce_summary_draft(payload: dict, medical_data: MedicalData) -> SummaryDraft:
    summary = str(payload.get("summary", "") or "").strip()
    if not summary.startswith(DISCLAIMER):
        summary = f"{DISCLAIMER}\n\n{summary}" if summary else DISCLAIMER
    summary = _strip_uninvented_medications(summary, medical_data)

    used_topics_raw = payload.get("used_topics") or []
    used_topics = [str(t).strip() for t in used_topics_raw if str(t).strip()] if isinstance(used_topics_raw, list) else []

    return SummaryDraft(disclaimer=DISCLAIMER, summary=summary, used_topics=used_topics)


def _gemini_summarize(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> SummaryDraft | None:
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
                HumanMessage(content=build_user_prompt(patient_data, medical_data, retrieved_docs)),
            ]
        )
        text = response.content if isinstance(response.content, str) else str(response.content)
        payload = _parse_json_response(text)
        if payload is None:
            logger.warning("Gemini summary generation returned non-JSON output; falling back")
            return None
        return _coerce_summary_draft(payload, medical_data)
    except Exception as exc:  # noqa: BLE001 - any provider/timeout error triggers fallback
        logger.warning("Gemini summary generation failed (%s); falling back to heuristics", exc)
        return None


def create_indepth_summary(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> SummaryDraft:
    """Grounded in-depth SOAP writeup from all three inputs. Do not emit recommendations."""
    settings = _get_settings()

    if settings.mock_llm or not settings.has_gemini:
        return build_indepth_summary_heuristic(patient_data, medical_data, retrieved_docs)

    result = _gemini_summarize(patient_data, medical_data, retrieved_docs)
    if result is not None:
        return result

    return build_indepth_summary_heuristic(patient_data, medical_data, retrieved_docs)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: python -m app.summarize.summary <patient.json> <medical.json> <docs.json>")
        raise SystemExit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        patient = PatientData.model_validate_json(fh.read())
    with open(sys.argv[2], "r", encoding="utf-8") as fh:
        medical = MedicalData.model_validate_json(fh.read())
    with open(sys.argv[3], "r", encoding="utf-8") as fh:
        docs_payload = json.load(fh)
    docs = [RetrievedDoc.model_validate(doc) for doc in docs_payload]

    draft = create_indepth_summary(patient, medical, docs)
    print(draft.summary)
