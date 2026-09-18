"""Heuristic recommendations when MOCK_LLM=true or the live LLM fails. Owned by Lakshmi."""

from __future__ import annotations

import re

from app.contracts import LabFlag, MedicalData, PatientData, Recommendation, RetrievedDoc

DISCLAIMER = "Educational prototype. Not for clinical use."
EMPTY_EVIDENCE_TITLE = "Guideline evidence was not retrieved; clinician review required."

_URGENT_TOKENS = (
    "sepsis",
    "septic",
    "troponin",
    "acs",
    "stemi",
    "nstemi",
    "myocardial",
    "chest pain",
)

_INVENTED_SOURCE_NAMES = ("NICE", "UpToDate", "NG28", "Cochrane Library")


def allowed_citation_strings(retrieved_docs: list[RetrievedDoc]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for doc in retrieved_docs:
        for value in (doc.citation, doc.title):
            text = (value or "").strip()
            if text and text not in seen:
                seen.add(text)
                values.append(text)
    return values


def top_doc(retrieved_docs: list[RetrievedDoc]) -> RetrievedDoc | None:
    if not retrieved_docs:
        return None
    return max(retrieved_docs, key=lambda doc: (doc.score, doc.title))


def citation_for(doc: RetrievedDoc) -> str:
    return (doc.citation or doc.title or "").strip()


def is_urgent(medical_data: MedicalData) -> bool:
    flags = {lab.flag for lab in medical_data.labs}
    if "critical_high" in flags or "critical_low" in flags:
        return True
    blob = " ".join(
        [
            medical_data.chief_concern,
            medical_data.assessment,
            medical_data.plan,
            *medical_data.problems,
        ]
    ).lower()
    return any(token in blob for token in _URGENT_TOKENS)


def _flagged_labs(medical_data: MedicalData) -> list[LabFlag]:
    return [lab for lab in medical_data.labs if lab.flag in {"high", "critical_high", "low", "critical_low"}]


def _lab_mention(medical_data: MedicalData) -> str:
    notable = [lab for lab in medical_data.labs if lab.flag in {"high", "critical_high"}]
    if not notable:
        return ""
    parts = [f"{lab.analyte} {lab.value} {lab.unit}".strip() + f" ({lab.flag})" for lab in notable]
    return " Also mention flagged labs: " + "; ".join(parts) + "."


def _diabetes_signal(medical_data: MedicalData, retrieved_docs: list[RetrievedDoc]) -> bool:
    blob = " ".join([*medical_data.problems, medical_data.chief_concern, medical_data.assessment]).lower()
    lab_hit = any("hba1c" in lab.analyte.lower() or "a1c" in lab.analyte.lower() for lab in medical_data.labs)
    doc_hit = any(
        "diabetes" in f"{doc.topic} {doc.title} {doc.text}".lower() or "hba1c" in doc.text.lower()
        for doc in retrieved_docs
    )
    return "diabetes" in blob or lab_hit or doc_hit


def diabetes_doc(retrieved_docs: list[RetrievedDoc]) -> RetrievedDoc | None:
    for doc in retrieved_docs:
        hay = f"{doc.topic} {doc.title} {doc.text}".lower()
        if "diabetes" in hay or "hba1c" in hay or "glycemic" in hay:
            return doc
    return None


def diabetes_signal(medical_data: MedicalData, retrieved_docs: list[RetrievedDoc]) -> bool:
    return _diabetes_signal(medical_data, retrieved_docs)


def _title_cite(doc: RetrievedDoc | None) -> list[str]:
    if doc is None:
        return []
    title = (doc.title or "").strip()
    return [title] if title else []


def _corpus_text(retrieved_docs: list[RetrievedDoc]) -> str:
    return " ".join(f"{doc.title} {doc.citation} {doc.text} {doc.source}" for doc in retrieved_docs)


def _strip_invented_source_names(text: str, retrieved_docs: list[RetrievedDoc]) -> str:
    corpus = _corpus_text(retrieved_docs)
    cleaned = text
    for name in _INVENTED_SOURCE_NAMES:
        if re.search(re.escape(name), corpus, flags=re.IGNORECASE):
            continue
        cleaned = re.sub(re.escape(name), "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _clean_rec(rec: Recommendation, retrieved_docs: list[RetrievedDoc]) -> Recommendation:
    return rec.model_copy(
        update={
            "title": _strip_invented_source_names(rec.title, retrieved_docs),
            "detail": _strip_invented_source_names(rec.detail, retrieved_docs),
            "citations": [_strip_invented_source_names(c, retrieved_docs) for c in rec.citations if c],
        }
    )


def build_heuristic_recommendations(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> list[Recommendation]:
    """Build list[Recommendation] without an LLM (MOCK_LLM=true and live fallback)."""
    who = patient_data.name or "this synthetic patient"
    labs_note = _lab_mention(medical_data)

    if not retrieved_docs:
        return [
            _clean_rec(
                Recommendation(
                    title=EMPTY_EVIDENCE_TITLE,
                    detail=(
                        f"{DISCLAIMER} Discuss documented findings for {who} with a clinician. "
                        "Guideline evidence was not retrieved, so no source titles are listed."
                        f"{labs_note}"
                    ),
                    citations=[],
                ),
                [],
            )
        ]

    recs: list[Recommendation] = []

    if is_urgent(medical_data):
        recs.append(
            Recommendation(
                title="Discuss immediately with a clinician",
                detail=(
                    f"{DISCLAIMER} Consider discussing {who}'s critical-sounding findings "
                    f"({', '.join(medical_data.problems) or medical_data.chief_concern or 'see medical data'}) "
                    f"promptly.{labs_note} This is a discussion point, not an order for tests or treatment."
                ),
                citations=_title_cite(top_doc(retrieved_docs)),
            )
        )

    diabetes_card = diabetes_doc(retrieved_docs)
    if _diabetes_signal(medical_data, retrieved_docs) and diabetes_card:
        hba1c = next(
            (lab for lab in medical_data.labs if "hba1c" in lab.analyte.lower() or "a1c" in lab.analyte.lower()),
            None,
        )
        hba1c_text = f" Documented HbA1c is {hba1c.value}{(' ' + hba1c.unit) if hba1c.unit else ''}." if hba1c else ""
        recs.append(
            Recommendation(
                title="Discuss glycemic follow-up and HbA1c trend",
                detail=(
                    f"{DISCLAIMER} Consider reviewing glycemic follow-up for {who}.{hba1c_text} "
                    f"Use the retrieved diabetes teaching card as discussion context only.{labs_note}"
                ),
                citations=_title_cite(diabetes_card),
            )
        )

    for doc in retrieved_docs:
        recs.append(
            Recommendation(
                title=f"Consider teaching points from {doc.title}",
                detail=(
                    f"{DISCLAIMER} Discuss how the retrieved card '{doc.title}' relates to "
                    f"{', '.join(medical_data.problems) or medical_data.chief_concern or 'the documented concerns'} "
                    f"for {who}.{labs_note} Do not invent labs or medications beyond the inputs."
                ),
                citations=_title_cite(doc),
            )
        )

    for lab in _flagged_labs(medical_data):
        recs.append(
            Recommendation(
                title=f"Discuss flagged {lab.analyte} result",
                detail=(
                    f"{DISCLAIMER} Consider discussing {lab.analyte} {lab.value} {lab.unit}".strip()
                    + f" (flag {lab.flag}) for {who}. This is not an order to repeat or treat the lab."
                ),
                citations=_title_cite(top_doc(retrieved_docs)),
            )
        )

    if medical_data.medications:
        recs.append(
            Recommendation(
                title="Discuss currently listed medications",
                detail=(
                    f"{DISCLAIMER} Consider reviewing adherence and follow-up for documented medications "
                    f"({', '.join(medical_data.medications)}) only. Do not add drugs that are not in the inputs."
                ),
                citations=_title_cite(top_doc(retrieved_docs)),
            )
        )

    recs.append(
        Recommendation(
            title="Consider clinician-led follow-up planning",
            detail=(
                f"{DISCLAIMER} Discuss next educational follow-up for {who} based only on the listed "
                f"concern ({medical_data.chief_concern or 'not documented'}) and retrieved teaching cards."
            ),
            citations=_title_cite(top_doc(retrieved_docs)),
        )
    )

    cleaned = [_clean_rec(rec, retrieved_docs) for rec in recs]
    return _dedupe_cap(cleaned, min_count=3, max_count=6)


def _dedupe_cap(recs: list[Recommendation], min_count: int, max_count: int) -> list[Recommendation]:
    unique: list[Recommendation] = []
    seen: set[str] = set()
    for rec in recs:
        key = rec.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(rec)
    if len(unique) >= min_count:
        return unique[:max_count]
    return unique
