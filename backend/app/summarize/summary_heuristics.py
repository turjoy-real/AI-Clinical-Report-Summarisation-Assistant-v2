"""Heuristic (non-LLM) in-depth SOAP summary writer. Owned by Sneha.

Used when MOCK_LLM=true and as the fallback when the Gemini/LangChain path
fails or times out. Builds the summary from patient_data, medical_data, and
retrieved_docs only -- never invents a lab, medication, diagnosis, or plan
item that is not already present in those inputs.
"""

from __future__ import annotations

from app.contracts import LabFlag, MedicalData, PatientData, RetrievedDoc, SummaryDraft

DISCLAIMER = "Educational prototype. Not for clinical use."


def _format_lab(lab: LabFlag) -> str:
    unit = f" {lab.unit}".rstrip() if lab.unit else ""
    return f"{lab.analyte} {lab.value}{unit} ({lab.flag})"


def _subjective(patient_data: PatientData, medical_data: MedicalData) -> str:
    who_bits: list[str] = []
    if patient_data.age is not None:
        who_bits.append(f"{patient_data.age}-year-old")
    if patient_data.sex:
        who_bits.append(patient_data.sex)
    who = " ".join(who_bits) if who_bits else "patient (age/sex not documented)"
    setting = patient_data.setting or "an undocumented setting"
    concern = medical_data.chief_concern or "not documented"
    return f"{who} seen in {setting}. Chief concern: {concern}."


def _objective(medical_data: MedicalData) -> str:
    if medical_data.vitals:
        vitals = ", ".join(f"{name} {value}" for name, value in medical_data.vitals.items())
    else:
        vitals = "not documented"
    if medical_data.labs:
        labs = ", ".join(_format_lab(lab) for lab in medical_data.labs)
    else:
        labs = "not documented"
    return f"Vitals: {vitals}. Labs: {labs}."


def _assessment(medical_data: MedicalData) -> str:
    if medical_data.assessment:
        return medical_data.assessment
    if medical_data.problems:
        return "Problems: " + ", ".join(medical_data.problems) + "."
    return "Assessment not documented."


def _plan(medical_data: MedicalData) -> str:
    return medical_data.plan or "Plan not documented in the source note."


def _evidence_used(retrieved_docs: list[RetrievedDoc]) -> str:
    titles = [doc.title for doc in retrieved_docs if doc.title]
    if not titles:
        return "No guideline evidence retrieved for this case."
    return "\n".join(f"- {title}" for title in titles)


def _mentioned_topics(retrieved_docs: list[RetrievedDoc], haystack: str) -> list[str]:
    lowered = haystack.lower()
    ordered: list[str] = []
    for doc in retrieved_docs:
        topic = doc.topic
        if topic and topic.lower().replace("_", " ") in lowered and topic not in ordered:
            ordered.append(topic)
    return ordered


def build_indepth_summary_heuristic(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> SummaryDraft:
    subjective = _subjective(patient_data, medical_data)
    objective = _objective(medical_data)
    assessment = _assessment(medical_data)
    plan = _plan(medical_data)
    evidence = _evidence_used(retrieved_docs)

    body = "\n\n".join(
        [
            "## Subjective",
            subjective,
            "## Objective",
            objective,
            "## Assessment",
            assessment,
            "## Plan",
            plan,
            "## Evidence used",
            evidence,
        ]
    )
    summary = f"{DISCLAIMER}\n\n{body}"
    used_topics = _mentioned_topics(retrieved_docs, " ".join([subjective, objective, assessment, plan]))
    return SummaryDraft(disclaimer=DISCLAIMER, summary=summary, used_topics=used_topics)
