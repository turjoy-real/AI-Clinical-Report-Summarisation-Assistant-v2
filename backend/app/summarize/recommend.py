from __future__ import annotations

from app.contracts import MedicalData, PatientData, Recommendation, RetrievedDoc


def create_recommendations(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> list[Recommendation]:
    # Replace stub — owned by Lakshmi
    citations = [doc.citation or doc.title for doc in retrieved_docs if doc.citation or doc.title]
    if not citations:
        citations = ["Educational prototype teaching card"]
    details = (
        f"Discuss follow-up for {', '.join(medical_data.problems) or 'the listed concerns'} "
        f"with {patient_data.name}. Do not auto-order medications or imaging. "
        "Educational prototype. Not for clinical use."
    )
    return [
        Recommendation(
            title="Clinician discussion points",
            detail=details,
            citations=citations[:3],
        )
    ]
