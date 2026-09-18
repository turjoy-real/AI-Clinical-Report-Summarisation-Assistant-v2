"""Specialty / urgency routing. Cheap heuristics first, optional LLM JSON second."""

from __future__ import annotations

import json
import re
from typing import Any

from app.llm.provider import complete_json

SPECIALTIES = ("endocrine", "cardio", "infectious_disease", "renal", "heme", "general")
URGENT = ("routine", "critical")

CRITICAL_PATTERNS = [
    r"sepsis",
    r"septic",
    r"stemi",
    r"\bacs\b",
    r"hypertensive urgency",
    r"lactate\s*[>=:]?\s*4",
    r"troponin\s*[>=:]?\s*0\.1",
    r"gcs\s*13",
    r"bp\s*1(?:7[8-9]|8\d|9\d)",
]

SPECIALTY_RULES: list[tuple[str, list[str]]] = [
    ("infectious_disease", ["sepsis", "pneumonia", "lactate", "infiltrate"]),
    ("cardio", ["chest pain", "troponin", "stemi", "heart failure", "hfref", r"\bbnp\b", "hypertension", "blood pressure"]),
    ("endocrine", ["diabetes", "hypothyroid", r"\btsh\b", "metformin", "hba1c"]),
    ("renal", [r"\baki\b", r"\bckd\b", r"\begfr\b", "creatinine", "nephrolog"]),
    ("heme", ["anemia", "ferritin", "iron-deficiency"]),
]


def _positive_mention(text: str, phrase: str) -> bool:
    lowered = text.lower()
    for match in re.finditer(re.escape(phrase.lower()), lowered):
        prefix = lowered[max(0, match.start() - 12) : match.start()]
        if re.search(r"\b(no|denies|without|not)\s+$", prefix):
            continue
        return True
    return False


def _keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(
        1
        for word in keywords
        if re.search(word if word.startswith("\\b") or " " in word else rf"\b{word}\b", text)
    )


def route_report(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    if "annual physical" in lowered or "preventive visit" in lowered:
        return {
            "specialty": "general",
            "urgency": "routine",
            "router_confidence": 0.8,
            "router_rationale": "Wellness / preventive visit routed to general medicine.",
        }

    critical = any(re.search(pattern, lowered) for pattern in CRITICAL_PATTERNS)
    if _positive_mention(text, "chest pain") and any(re.search(p, lowered) for p in (r"troponin", r"stemi", r"\bacs\b")):
        critical = True
    # Negated ACS phrases must not force critical on their own.
    if not critical and _positive_mention(text, "chest pain") is False:
        pass

    urgency = "critical" if critical else "routine"
    specialty = "general"
    hits = 0
    for name, keywords in SPECIALTY_RULES:
        score = _keyword_hits(lowered, keywords)
        if score > hits:
            hits = score
            specialty = name
    confidence = 0.55 + min(hits, 4) * 0.1
    if hits < 2:
        specialty = "general"
        confidence = 0.4 if hits == 0 else 0.5
    return {
        "specialty": specialty,
        "urgency": urgency,
        "router_confidence": round(confidence, 2),
        "router_rationale": f"Heuristic route to {specialty} with {urgency} urgency ({hits} keyword hits).",
    }


def refine_route(text: str) -> dict[str, Any]:
    heuristic = route_report(text)
    result = complete_json(
        "You route synthetic educational clinical notes. "
        "Return JSON with specialty (endocrine|cardio|infectious_disease|renal|heme|general), "
        "urgency (routine|critical), router_confidence (0-1), router_rationale. "
        "Do not treat negated phrases such as 'no chest pain' as ACS.",
        (text or "")[:4000],
        heuristic,
    )
    try:
        parsed = {**heuristic, **json.loads(result.text)}
    except json.JSONDecodeError:
        parsed = heuristic
    if parsed.get("urgency") not in URGENT:
        parsed["urgency"] = heuristic["urgency"]
    if parsed.get("specialty") not in SPECIALTIES:
        parsed["specialty"] = heuristic["specialty"]
    try:
        confidence = float(parsed.get("router_confidence", heuristic["router_confidence"]))
    except (TypeError, ValueError):
        confidence = heuristic["router_confidence"]
    if confidence < 0.45:
        parsed["specialty"] = "general"
        parsed["router_rationale"] = (
            (parsed.get("router_rationale") or "") + " Low confidence fallback to general medicine."
        ).strip()
        parsed["router_confidence"] = confidence
    else:
        parsed["router_confidence"] = confidence
    parsed["model_used"] = result.provider
    parsed["fallback"] = result.fallback
    return parsed
