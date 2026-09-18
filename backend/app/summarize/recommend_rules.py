"""LK3 citation, urgency, medication, and identifier rules. Owned by Lakshmi."""

from __future__ import annotations

import re

from app.contracts import MedicalData, PatientData, Recommendation, RetrievedDoc
from app.summarize.recommend_heuristics import (
    DISCLAIMER,
    citation_for,
    diabetes_doc,
    diabetes_signal,
    is_urgent,
)

IMMEDIATE_TITLE = "Discuss immediately with a clinician"

_ORDER_VERBS = ("prescribe", "start ", "initiate", "order ", "add ", "dispense", "titrate to")
_TEACHING_MARKERS = ("discuss", "consider", "teaching", "educational")

# Tokens used only to catch invented drug advice; listed meds always allowed.
_MED_TOKENS = (
    "metformin",
    "insulin",
    "semaglutide",
    "liraglutide",
    "dulaglutide",
    "exenatide",
    "tirzepatide",
    "empagliflozin",
    "dapagliflozin",
    "canagliflozin",
    "sitagliptin",
    "linagliptin",
    "gliclazide",
    "glipizide",
    "glimepiride",
    "glyburide",
    "pioglitazone",
    "sulfonylurea",
    "sglt2",
    "glp-1",
    "glp1",
    "dpp-4",
    "statin",
    "atorvastatin",
    "simvastatin",
    "rosuvastatin",
    "pravastatin",
    "lisinopril",
    "amlodipine",
    "losartan",
    "warfarin",
    "apixaban",
    "rivaroxaban",
    "amiodarone",
    "aspirin",
    "clopidogrel",
    "vancomycin",
    "ceftriaxone",
    "piperacillin",
    "meropenem",
    "norepinephrine",
    "dobutamine",
    "heparin",
    "enoxaparin",
)


def apply_lk3_rules(
    recs: list[Recommendation],
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
    pad_with: list[Recommendation] | None = None,
) -> list[Recommendation]:
    cleaned = [_strip_extra_identifiers(rec, patient_data) for rec in recs]
    cleaned = [rec for rec in cleaned if _medication_allowed(rec, medical_data, retrieved_docs)]
    cleaned = _ensure_urgent_first(cleaned, patient_data, medical_data, retrieved_docs)
    cleaned = _ensure_glycemic_diabetes_card(cleaned, patient_data, medical_data, retrieved_docs)
    cleaned = [_strip_extra_identifiers(rec, patient_data) for rec in cleaned]
    cleaned = [rec for rec in cleaned if _medication_allowed(rec, medical_data, retrieved_docs)]

    if not retrieved_docs:
        return cleaned[:1]
    if len(cleaned) < 3:
        extras = [
            rec
            for rec in (pad_with or [])
            if _medication_allowed(rec, medical_data, retrieved_docs)
        ]
        extras = [_strip_extra_identifiers(rec, patient_data) for rec in extras]
        cleaned = _merge_unique(cleaned, extras)
        cleaned = _ensure_urgent_first(cleaned, patient_data, medical_data, retrieved_docs)
        cleaned = _ensure_glycemic_diabetes_card(cleaned, patient_data, medical_data, retrieved_docs)
    return cleaned[:6]


def _merge_unique(
    recs: list[Recommendation], extras: list[Recommendation]
) -> list[Recommendation]:
    out: list[Recommendation] = []
    seen: set[str] = set()
    for rec in [*recs, *extras]:
        key = rec.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def _ensure_urgent_first(
    recs: list[Recommendation],
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> list[Recommendation]:
    if not retrieved_docs or not is_urgent(medical_data):
        return recs
    who = patient_data.name or "this synthetic patient"
    immediate = Recommendation(
        title=IMMEDIATE_TITLE,
        detail=(
            f"{DISCLAIMER} Consider discussing {who}'s critical-sounding findings "
            f"({', '.join(medical_data.problems) or medical_data.chief_concern or 'see medical data'}) "
            "promptly. This is a discussion point, not an order for tests or treatment."
        ),
        citations=_diabetes_or_top_citations(retrieved_docs),
    )
    rest = [rec for rec in recs if rec.title.strip().lower() != IMMEDIATE_TITLE.lower()]
    return [immediate, *rest]


def _ensure_glycemic_diabetes_card(
    recs: list[Recommendation],
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> list[Recommendation]:
    card = diabetes_doc(retrieved_docs)
    if not card or not diabetes_signal(medical_data, retrieved_docs):
        return recs
    cite = citation_for(card)
    allowed = {cite, card.title.strip()} - {""}

    def _is_glycemic(rec: Recommendation) -> bool:
        blob = f"{rec.title} {rec.detail}".lower()
        cites_card = bool(set(rec.citations) & allowed)
        return cites_card and ("glycemic" in blob or "hba1c" in blob or "a1c" in blob)

    if any(_is_glycemic(rec) for rec in recs):
        return recs

    who = patient_data.name or "this synthetic patient"
    hba1c = next(
        (lab for lab in medical_data.labs if "hba1c" in lab.analyte.lower() or "a1c" in lab.analyte.lower()),
        None,
    )
    hba1c_text = (
        f" Documented HbA1c is {hba1c.value}{(' ' + hba1c.unit) if hba1c and hba1c.unit else ''}."
        if hba1c
        else ""
    )
    glycemic = Recommendation(
        title="Discuss glycemic follow-up and HbA1c trend",
        detail=(
            f"{DISCLAIMER} Consider reviewing glycemic follow-up for {who}.{hba1c_text} "
            "Use the retrieved diabetes teaching card as discussion context only."
        ),
        citations=[cite] if cite else [card.title],
    )
    if recs and recs[0].title.strip().lower() == IMMEDIATE_TITLE.lower():
        return [recs[0], glycemic, *recs[1:]]
    return [glycemic, *recs]


def _diabetes_or_top_citations(retrieved_docs: list[RetrievedDoc]) -> list[str]:
    card = diabetes_doc(retrieved_docs)
    if card:
        value = citation_for(card)
        return [value] if value else []
    if retrieved_docs:
        value = (retrieved_docs[0].citation or retrieved_docs[0].title or "").strip()
        return [value] if value else []
    return []


def _medication_allowed(
    rec: Recommendation,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> bool:
    listed = " ".join(medical_data.medications).lower()
    evidence = " ".join(f"{doc.title} {doc.text}" for doc in retrieved_docs).lower()
    blob = f"{rec.title} {rec.detail}".lower()
    teaching = any(marker in blob for marker in _TEACHING_MARKERS)
    ordering = _looks_like_prescription(blob)

    for token in _MED_TOKENS:
        if token not in blob:
            continue
        if token in listed or any(token in med.lower() or med.lower() in token for med in medical_data.medications):
            continue
        if token in evidence and teaching and not ordering:
            continue
        return False
    return True


def _looks_like_prescription(blob: str) -> bool:
    if any(phrase in blob for phrase in ("not an order", "not a prescription", "not prescribing")):
        return any(verb in blob for verb in ("prescribe", "initiate", "dispense"))
    return any(verb in blob for verb in _ORDER_VERBS)


def _strip_extra_identifiers(rec: Recommendation, patient_data: PatientData) -> Recommendation:
    title = rec.title
    detail = rec.detail
    secrets = [patient_data.mrn, patient_data.source_case_id]
    for secret in secrets:
        if not secret:
            continue
        title = re.sub(re.escape(secret), "", title, flags=re.IGNORECASE)
        detail = re.sub(re.escape(secret), "", detail, flags=re.IGNORECASE)
    title = re.sub(r"\bMRN\b[:\s-]*", "", title, flags=re.IGNORECASE)
    detail = re.sub(r"\bMRN\b[:\s-]*", "", detail, flags=re.IGNORECASE)
    title = re.sub(r"\s{2,}", " ", title).strip(" ,;-")
    detail = re.sub(r"\s{2,}", " ", detail).strip()
    return rec.model_copy(update={"title": title, "detail": detail})
