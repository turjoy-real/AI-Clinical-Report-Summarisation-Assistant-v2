from __future__ import annotations

from app.contracts import MedicalData, PatientData, RetrievedDoc, SummaryDraft


def create_indepth_summary(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> SummaryDraft:
    # Replace stub — owned by Sneha
    labs = ", ".join(f"{lab.analyte} {lab.value} {lab.unit}".strip() for lab in medical_data.labs) or "none listed"
    problems = ", ".join(medical_data.problems) or "none listed"
    topics = [doc.topic for doc in retrieved_docs]
    summary = (
        "Educational prototype. Not for clinical use. "
        f"SOAP-style stub for {patient_data.name} (MRN {patient_data.mrn or 'synthetic-unknown'}). "
        f"Subjective: {medical_data.chief_concern or 'see note'}. "
        f"Problems include {problems}. Labs reviewed: {labs}. "
        "Objective and assessment stay grounded to the uploaded synthetic note. "
        "Plan is discussion-only until a clinician approves the draft."
    )
    return SummaryDraft(summary=summary, used_topics=topics)
