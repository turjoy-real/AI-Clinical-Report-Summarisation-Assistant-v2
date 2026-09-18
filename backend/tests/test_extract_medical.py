from __future__ import annotations

from pathlib import Path

from app.contracts import MedicalData
from app.extract.medical import extract_medical_data

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"


def _read(case_id: str) -> str:
    return (DATA_DIR / f"{case_id}.md").read_text(encoding="utf-8")


def test_cr001_diabetes_labs_and_medications():
    result = extract_medical_data(_read("CR-001"))
    assert isinstance(result, MedicalData)

    problems_lower = " ".join(result.problems).lower()
    assert "diabetes" in problems_lower

    analytes = [lab.analyte.lower() for lab in result.labs]
    assert any("hba1c" in a or "a1c" in a for a in analytes)

    hba1c_labs = [lab for lab in result.labs if "hba1c" in lab.analyte.lower() or "a1c" in lab.analyte.lower()]
    assert any("9.2" in lab.value for lab in hba1c_labs)

    medications_lower = " ".join(result.medications).lower()
    assert "metformin" in medications_lower


def test_cr001_problems_do_not_contain_patient_name():
    result = extract_medical_data(_read("CR-001"))
    problems_lower = " ".join(result.problems).lower()
    assert "jordan" not in problems_lower
    assert "hale" not in problems_lower


def test_cr005_wellness_note_does_not_crash():
    result = extract_medical_data(_read("CR-005"))
    assert isinstance(result, MedicalData)
    # No requirement for critical_high flags on a normal wellness visit.
    assert not any(lab.flag == "critical_high" for lab in result.labs)


def test_cr011_unreadable_note_sets_missing_sections():
    result = extract_medical_data(_read("CR-011"))
    assert isinstance(result, MedicalData)
    assert len(result.missing_sections) > 0


def test_empty_document_returns_defaults():
    result = extract_medical_data("")
    assert isinstance(result, MedicalData)
    assert result == MedicalData()


def test_return_type_is_medical_data():
    result = extract_medical_data(_read("CR-001"))
    assert isinstance(result, MedicalData)
