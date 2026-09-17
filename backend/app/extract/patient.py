from __future__ import annotations

import re

from app.contracts import PatientData


def extract_patient_data(document_text: str) -> PatientData:
    # Replace stub — owned by Radhakrishna
    text = document_text or ""
    mrn_match = re.search(r"SYN-\d+", text)
    name = "synthetic-unknown"
    name_match = re.search(r"Patient:\s*([^(\n]+)", text)
    if name_match:
        name = name_match.group(1).strip().rstrip(",")
    age_match = re.search(r"(\d{1,3})-year-old", text)
    setting = None
    lowered = text.lower()
    if "clinic" in lowered:
        setting = "clinic"
    elif " ed" in lowered or "emergency" in lowered:
        setting = "ED"
    return PatientData(
        name=name or "synthetic-unknown",
        age=int(age_match.group(1)) if age_match else None,
        mrn=mrn_match.group(0) if mrn_match else None,
        setting=setting,
        source_case_id="CR-001" if "SYN-1001" in text else None,
    )
