"""Offline, demographics-only extraction helpers."""

from __future__ import annotations

import re

from app.contracts import PatientData


def extract_patient_heuristics(document_text: str) -> PatientData:
    """Extract explicit demographics without making clinical inferences."""
    text = document_text or ""
    if not text.strip():
        return PatientData()

    def field(pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip().rstrip(" ,") if match else None

    name = field(r"^\s*Patient:\s*([^\n,(]+)") or "synthetic-unknown"
    age_match = re.search(r"\b(\d{1,3})\s*-?year-old\b", text, re.IGNORECASE)
    sex = field(r"^\s*Sex:\s*([^\n]+)")
    if sex is None:
        sex_match = re.search(r"\b(male|female|man|woman|non-?binary)\b", text, re.IGNORECASE)
        sex = sex_match.group(1) if sex_match else None
    mrn_match = re.search(r"\bSYN-\d+\b", text, re.IGNORECASE)
    date = field(r"^\s*Date:\s*([^\n]+)")
    case_match = re.search(r"\b(CR-\d{3})\b", text)
    lowered = text.lower()
    setting = None
    explicit_setting = field(r"^\s*Setting:\s*([^\n]+)")
    if explicit_setting:
        if "clinic" in explicit_setting.lower():
            setting = "clinic"
        elif "emergency" in explicit_setting.lower() or re.search(r"\bed\b", explicit_setting, re.I):
            setting = "ED"
        elif "ward" in explicit_setting.lower() or "inpatient" in explicit_setting.lower():
            setting = "ward"
        else:
            setting = explicit_setting
    elif "clinic" in lowered:
        setting = "clinic"
    elif "emergency" in lowered or re.search(r"\bED\b", text):
        setting = "ED"
    elif "ward" in lowered or "inpatient" in lowered:
        setting = "ward"

    return PatientData(name=name, age=int(age_match.group(1)) if age_match else None,
        sex=sex, mrn=mrn_match.group(0).upper() if mrn_match else None, setting=setting,
        date=date, source_case_id=case_match.group(1) if case_match else None)
