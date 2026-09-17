from __future__ import annotations

from pathlib import Path

from app.contracts import PatientData
from app.extract.patient import extract_patient_data


ROOT = Path(__file__).resolve().parents[2]


def test_cr001_demographics_are_extracted():
    patient = extract_patient_data((ROOT / "data/reports/CR-001.md").read_text(encoding="utf-8"))
    assert patient.name == "Jordan Hale"
    assert patient.mrn == "SYN-1001"
    assert patient.age == 58
    assert patient.setting == "clinic"


def test_patient_data_does_not_include_medical_content():
    patient = extract_patient_data((ROOT / "data/reports/CR-001.md").read_text(encoding="utf-8"))
    values = " ".join(str(value).lower() for value in patient.model_dump().values())
    assert "hba1c" not in values and "metformin" not in values and "diabetes" not in values


def test_unreadable_note_does_not_crash():
    patient = extract_patient_data((ROOT / "data/reports/CR-011.md").read_text(encoding="utf-8"))
    assert isinstance(patient, PatientData)


def test_empty_note_returns_defaults():
    assert extract_patient_data("") == PatientData()
