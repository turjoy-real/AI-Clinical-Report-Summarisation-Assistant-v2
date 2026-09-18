"""Cited educational recommendations. Owned by Lakshmi.

Public API: create_recommendations. Do not call SOAP or RAG from here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.contracts import MedicalData, PatientData, Recommendation, RetrievedDoc
from app.summarize.recommend_heuristics import (
    allowed_citation_strings,
    build_heuristic_recommendations,
    top_doc,
)
from app.summarize.recommend_prompt import SYSTEM_PROMPT
from app.summarize.recommend_rules import apply_lk3_rules

LLM_TEMPERATURE = 0.1


def create_recommendations(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> list[Recommendation]:
    """Cited follow-up discussion points from all three inputs. Do not rewrite the SOAP summary."""
    mock_recs = build_heuristic_recommendations(patient_data, medical_data, retrieved_docs)
    settings = get_settings()
    if not settings.use_live_llm:
        return _finalize(mock_recs, patient_data, medical_data, retrieved_docs)

    try:
        live_recs = _live_recommendations(patient_data, medical_data, retrieved_docs)
    except Exception:
        return _finalize(mock_recs, patient_data, medical_data, retrieved_docs)

    if not live_recs:
        return _finalize(mock_recs, patient_data, medical_data, retrieved_docs)
    return _finalize(live_recs, patient_data, medical_data, retrieved_docs, pad_with=mock_recs)


def _live_recommendations(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> list[Recommendation]:
    from langchain_core.prompts import ChatPromptTemplate

    llm = _build_langchain_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{user_payload}"),
        ]
    )
    messages = prompt.format_messages(
        user_payload=_user_payload(patient_data, medical_data, retrieved_docs)
    )
    response = llm.invoke(messages)
    return _parse_recommendations(_message_text(response))


def _build_langchain_llm() -> Any:
    settings = get_settings()
    if settings.has_gemini:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=LLM_TEMPERATURE,
        )
    if settings.has_openai:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=LLM_TEMPERATURE,
        )
    raise RuntimeError("No LLM key configured")


def _user_payload(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> str:
    evidence = [
        {
            "title": doc.title,
            "topic": doc.topic,
            "text": doc.text,
            "citation": doc.citation or doc.title,
        }
        for doc in retrieved_docs
    ]
    return (
        "Ask: return a JSON list of Recommendation objects "
        "(each: title, detail, citations). No SOAP summary.\n\n"
        f"PATIENT_JSON\n{patient_data.model_dump_json()}\n\n"
        f"MEDICAL_JSON\n{medical_data.model_dump_json()}\n\n"
        "EVIDENCE_CHUNKS: {title, topic, text, citation}\n"
        f"{json.dumps(evidence)}\n"
    )


def _message_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts)
    return str(content or "")


def _parse_recommendations(text: str) -> list[Recommendation]:
    try:
        payload = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(payload, dict) and "recommendations" in payload:
        payload = payload["recommendations"]
    if not isinstance(payload, list):
        return []
    recs: list[Recommendation] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            recs.append(Recommendation.model_validate(item))
        except Exception:
            continue
    return recs


def _extract_json(text: str) -> Any:
    blob = (text or "").strip()
    if blob.startswith("```"):
        lines = blob.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        blob = "\n".join(lines).strip()
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        start = blob.find("[")
        end = blob.rfind("]")
        if start != -1 and end > start:
            return json.loads(blob[start : end + 1])
        raise


def lock_citations(recs: list[Recommendation], retrieved_docs: list[RetrievedDoc]) -> list[Recommendation]:
    """Strip citations not present on retrieved_docs; refill empty recs with top-scoring title."""
    allowed = set(allowed_citation_strings(retrieved_docs))
    ranked = top_doc(retrieved_docs)
    fallback_title = (ranked.title or "").strip() if ranked else ""
    locked: list[Recommendation] = []
    for rec in recs:
        kept = [c for c in rec.citations if c in allowed]
        if not kept and retrieved_docs and fallback_title:
            kept = [fallback_title]
        locked.append(rec.model_copy(update={"citations": kept}))
    return locked


def _finalize(
    recs: list[Recommendation],
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
    pad_with: list[Recommendation] | None = None,
) -> list[Recommendation]:
    locked = lock_citations(recs, retrieved_docs)
    locked_pad = lock_citations(pad_with, retrieved_docs) if pad_with else None
    return apply_lk3_rules(
        locked,
        patient_data,
        medical_data,
        retrieved_docs,
        pad_with=locked_pad,
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_patient(raw: Any) -> PatientData:
    if isinstance(raw, dict) and "name" not in raw and "patient" in raw:
        raw = raw["patient"]
    return PatientData.model_validate(raw)


def _load_medical(raw: Any) -> MedicalData:
    if isinstance(raw, dict) and "MEDICAL" in raw:
        raw = raw["MEDICAL"]
    elif isinstance(raw, dict) and "medical" in raw and "labs" not in raw:
        raw = raw["medical"]
    return MedicalData.model_validate(raw)


def _load_docs(raw: Any) -> list[RetrievedDoc]:
    if isinstance(raw, dict):
        raw = raw.get("retrieved_docs") or raw.get("docs") or []
    return [RetrievedDoc.model_validate(item) for item in raw]


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m app.summarize.recommend patient.json medical.json docs.json"""
    parser = argparse.ArgumentParser(
        description="Print cited educational recommendations as JSON. Demo without the UI."
    )
    parser.add_argument("patient_json", type=Path)
    parser.add_argument("medical_json", type=Path)
    parser.add_argument("docs_json", type=Path)
    args = parser.parse_args(argv)

    patient = _load_patient(_load_json(args.patient_json))
    medical = _load_medical(_load_json(args.medical_json))
    docs = _load_docs(_load_json(args.docs_json))
    recs = create_recommendations(patient, medical, docs)
    print(json.dumps([rec.model_dump() for rec in recs], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
