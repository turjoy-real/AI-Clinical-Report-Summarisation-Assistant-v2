from __future__ import annotations

from pathlib import Path

from app.contracts import MedicalData, PatientData, RetrievedDoc, SummaryDraft
from app.extract.medical import extract_medical_data
from app.extract.patient import extract_patient_data
from app.summarize.summary import create_indepth_summary

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"


def _read(case_id: str) -> str:
    return (DATA_DIR / f"{case_id}.md").read_text(encoding="utf-8")


def _diabetes_doc() -> RetrievedDoc:
    return RetrievedDoc(
        id="diabetes-1",
        title="Type 2 Diabetes Management",
        topic="diabetes",
        source="diabetes.md",
        text="HbA1c targets and metformin as first-line therapy for type 2 diabetes.",
        score=0.9,
        citation="Educational diabetes teaching card",
    )


def test_cr001_summary_mentions_diabetes_and_hba1c():
    patient = extract_patient_data(_read("CR-001"))
    medical = extract_medical_data(_read("CR-001"))
    draft = create_indepth_summary(patient, medical, [_diabetes_doc()])

    assert isinstance(draft, SummaryDraft)
    assert "diabetes" in draft.summary.lower()
    assert "9.2" in draft.summary


def test_cr001_summary_does_not_mention_unrelated_topic():
    patient = extract_patient_data(_read("CR-001"))
    medical = extract_medical_data(_read("CR-001"))
    draft = create_indepth_summary(patient, medical, [_diabetes_doc()])

    assert "sepsis" not in draft.summary.lower()


def test_summary_does_not_invent_problems_not_in_medical_data():
    patient = PatientData(name="synthetic-unknown", age=54)
    medical = MedicalData(chief_concern="Follow-up visit", problems=["hypertension"])
    draft = create_indepth_summary(patient, medical, [])

    assert "diabetes" not in draft.summary.lower()
    assert "hypertension" in draft.summary.lower()


def test_summary_notes_missing_fields_instead_of_guessing():
    patient = PatientData()
    medical = MedicalData()
    draft = create_indepth_summary(patient, medical, [])

    assert "not documented" in draft.summary.lower()


def test_return_type_is_summary_draft():
    patient = PatientData()
    medical = MedicalData()
    draft = create_indepth_summary(patient, medical, [])

    assert isinstance(draft, SummaryDraft)
    assert not isinstance(draft, list)
    assert not hasattr(draft, "recommendations")


def test_disclaimer_present_and_first():
    patient = PatientData()
    medical = MedicalData()
    draft = create_indepth_summary(patient, medical, [])

    assert draft.disclaimer == "Educational prototype. Not for clinical use."
    assert draft.summary.startswith("Educational prototype. Not for clinical use.")
