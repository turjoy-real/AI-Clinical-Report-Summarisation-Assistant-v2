from __future__ import annotations

import re

from app.contracts import LabFlag, MedicalData


def extract_medical_data(document_text: str) -> MedicalData:
    # Replace stub — owned by Vinayak
    text = document_text or ""
    lowered = text.lower()
    problems: list[str] = []
    if "diabetes" in lowered:
        problems.append("type 2 diabetes")
    if "hypertension" in lowered or "blood pressure" in lowered:
        problems.append("hypertension")
    if "sepsis" in lowered:
        problems.append("suspected sepsis")
    medications: list[str] = []
    for med in ("metformin", "amlodipine", "lisinopril", "warfarin", "amiodarone", "simvastatin"):
        if med in lowered:
            medications.append(med)
    labs: list[LabFlag] = []
    a1c = re.search(r"hba1c\s*([0-9.]+)", lowered)
    if a1c:
        labs.append(LabFlag(analyte="HbA1c", value=a1c.group(1), unit="%", flag="high"))
    lactate = re.search(r"lactate\s*([0-9.]+)", lowered)
    if lactate:
        labs.append(LabFlag(analyte="lactate", value=lactate.group(1), unit="mmol/L", flag="critical_high"))
    concern = ""
    concern_match = re.search(r"Chief concern\s*\n(.+)", text)
    if concern_match:
        concern = concern_match.group(1).strip()
    return MedicalData(
        chief_concern=concern,
        problems=problems,
        medications=medications,
        labs=labs,
        assessment="Heuristic stub assessment. Educational prototype. Not for clinical use.",
    )
