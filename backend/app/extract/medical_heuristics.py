"""Heuristic (non-LLM) medical extraction. Owned by Vinayak.

Used when MOCK_LLM=true and as the fallback when the Gemini/LangChain path
fails or times out. Must reliably parse the golden fixture CR-001 (diabetes,
HbA1c 9.2, metformin) without any network calls.
"""

from __future__ import annotations

import re

from app.contracts import LabFlag, MedicalData

_SECTION_HEADINGS = {
    "chief_concern": [r"chief concern", r"reason for visit"],
    "exam": [r"exam"],
    "results": [r"results", r"labs?\b"],
    "assessment": [r"assessment"],
    "plan": [r"plan"],
}

_PROBLEM_KEYWORDS = {
    "type 2 diabetes": ["type 2 diabetes", "diabetes mellitus", " diabetes"],
    "hypertension": ["hypertension", "blood pressure"],
    "obesity": ["obesity"],
    "hyperlipidemia": ["hyperlipidemia", "dyslipidemia"],
    "suspected sepsis": ["sepsis"],
    "asthma": ["asthma"],
    "copd": ["copd"],
    "atrial fibrillation": ["atrial fibrillation", "afib", "a-fib"],
    "chronic kidney disease": ["chronic kidney disease", "ckd"],
}

_MEDICATIONS = [
    "metformin",
    "amlodipine",
    "lisinopril",
    "warfarin",
    "amiodarone",
    "simvastatin",
    "atorvastatin",
    "insulin",
    "albuterol",
    "levothyroxine",
    "aspirin",
    "losartan",
]

_ALLERGY_MATCH = re.compile(r"allergies?\s*:?\s*(.+)", re.IGNORECASE)

# analyte name -> (regex for value, unit, normal range low/high for flagging)
_NUM = r"([0-9]+(?:\.[0-9]+)?)"

_LAB_PATTERNS: dict[str, tuple[str, str, tuple[float, float] | None]] = {
    "HbA1c": (rf"hba1c\s*{_NUM}\s*%?", "%", (4.0, 5.6)),
    "fasting glucose": (rf"fasting glucose\s*{_NUM}\s*mg/dl", "mg/dL", (70.0, 100.0)),
    "LDL": (rf"ldl\s*{_NUM}\s*mg/dl", "mg/dL", (0.0, 100.0)),
    "HDL": (rf"hdl\s*{_NUM}\s*mg/dl", "mg/dL", (40.0, 999.0)),
    "creatinine": (rf"creatinine\s*{_NUM}\s*mg/dl", "mg/dL", (0.6, 1.3)),
    "eGFR": (rf"egfr\s*{_NUM}", "", (60.0, 999.0)),
    "potassium": (rf"potassium\s*{_NUM}\s*mmol/l", "mmol/L", (3.5, 5.1)),
    "sodium": (rf"sodium\s*{_NUM}\s*mmol/l", "mmol/L", (135.0, 145.0)),
    "hemoglobin": (rf"hemoglobin\s*{_NUM}\s*g/dl", "g/dL", (12.0, 17.5)),
    "TSH": (rf"tsh\s*{_NUM}\s*miu/l", "mIU/L", (0.4, 4.0)),
    "lactate": (rf"lactate\s*{_NUM}\s*mmol/l", "mmol/L", (0.5, 2.2)),
}

_VITAL_PATTERNS = {
    "BP": r"BP\s*(\d{2,3}/\d{2,3})",
    "HR": r"HR\s*(\d{2,3})",
    "RR": r"RR\s*(\d{1,2})",
    "temperature": rf"temperature\s*{_NUM}\s*C",
    "BMI": rf"BMI\s*{_NUM}",
}


def _extract_section(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        # Match a heading line containing the keyword (e.g. "## Plan discussed"),
        # then capture everything up to the next heading or end of document.
        match = re.search(
            r"##[^\n]*" + pattern + r"[^\n]*\n(.+?)(?:\n##|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip()
    return ""


def _is_negated(lowered_text: str, term: str) -> bool:
    """True if every occurrence of `term` is inside a negated phrase like 'no insulin'."""
    for match in re.finditer(re.escape(term), lowered_text):
        window_start = max(0, match.start() - 40)
        preceding = lowered_text[window_start : match.start()]
        if not re.search(r"\bno\b[^.]*$", preceding):
            return False
    return True


def _flag_for(value: float, bounds: tuple[float, float] | None) -> str:
    if bounds is None:
        return "unknown"
    low, high = bounds
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "normal"


def extract_medical_heuristic(document_text: str) -> MedicalData:
    text = document_text or ""
    lowered = text.lower()

    if not text.strip():
        return MedicalData()

    # Unreadable / garbled source detection (e.g. CR-011 synthetic PDF garble).
    printable_ratio = sum(1 for ch in text if ch.isalnum() or ch.isspace()) / max(len(text), 1)
    if printable_ratio < 0.6 or "%pdf-unreadable" in lowered:
        return MedicalData(missing_sections=["unreadable_source"])

    chief_concern = _extract_section(text, _SECTION_HEADINGS["chief_concern"])
    assessment = _extract_section(text, _SECTION_HEADINGS["assessment"])
    plan = _extract_section(text, _SECTION_HEADINGS["plan"])
    results_block = _extract_section(text, _SECTION_HEADINGS["results"])

    problems: list[str] = []
    for problem, keywords in _PROBLEM_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            problems.append(problem)

    medications = [med for med in _MEDICATIONS if med in lowered and not _is_negated(lowered, med)]

    allergies: list[str] = []
    allergy_match = _ALLERGY_MATCH.search(text)
    if allergy_match:
        raw = allergy_match.group(1).strip()
        if raw and "none" not in raw.lower() and "nkda" not in raw.lower():
            allergies = [a.strip() for a in re.split(r",| and ", raw) if a.strip()]

    vitals: dict[str, str] = {}
    for name, pattern in _VITAL_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            vitals[name] = match.group(1)

    labs: list[LabFlag] = []
    for analyte, (pattern, unit, bounds) in _LAB_PATTERNS.items():
        match = re.search(pattern, lowered)
        if match:
            value_str = match.group(1)
            try:
                value_num = float(value_str)
                flag = _flag_for(value_num, bounds)
            except ValueError:
                flag = "unknown"
            labs.append(LabFlag(analyte=analyte, value=value_str, unit=unit, flag=flag))

    missing_sections: list[str] = []
    if not chief_concern:
        missing_sections.append("chief_concern")
    if not results_block and not labs:
        missing_sections.append("results")
    if not assessment:
        missing_sections.append("assessment")
    if not plan:
        missing_sections.append("plan")

    return MedicalData(
        chief_concern=chief_concern,
        problems=problems,
        medications=medications,
        allergies=allergies,
        vitals=vitals,
        labs=labs,
        assessment=assessment,
        plan=plan,
        missing_sections=missing_sections,
    )
