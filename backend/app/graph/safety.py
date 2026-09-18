"""Safety flags for educational drafts. Critical cases cannot skip HITL."""

from __future__ import annotations

import re
from typing import Any


def _positive_mention(text: str, phrase: str) -> bool:
    lowered = text.lower()
    for match in re.finditer(re.escape(phrase.lower()), lowered):
        prefix = lowered[max(0, match.start() - 12) : match.start()]
        if re.search(r"\b(no|denies|without|not)\s+$", prefix):
            continue
        return True
    return False


def _lab_is_critical(row: dict[str, Any]) -> bool:
    flag = str(row.get("flag") or row.get("severity") or "").lower()
    if flag in {"critical", "critical_high", "critical_low"}:
        return True
    analyte = str(row.get("analyte") or row.get("name") or "").lower()
    try:
        value = float(str(row.get("value") or "").split()[0])
    except (TypeError, ValueError):
        return False
    if analyte == "lactate" and value >= 4.0:
        return True
    if "troponin" in analyte and value >= 0.1:
        return True
    return False


def safety_flags_from_state(text: str, lab_flags: list[dict[str, Any]] | None = None) -> list[str]:
    flags: list[str] = []
    lowered = (text or "").lower()
    if _positive_mention(text, "sepsis") or "septic" in lowered:
        flags.append("possible_sepsis")
    if _positive_mention(text, "chest pain") or _positive_mention(text, "troponin"):
        flags.append("acs_symptoms")
    if "hypertensive urgency" in lowered or re.search(r"bp\s*1(?:7[8-9]|8\d)", lowered):
        flags.append("severe_hypertension")
    if any(_lab_is_critical(row) for row in lab_flags or []):
        flags.append("critical_labs")
    return sorted(set(flags))


def lock_hitl(urgency: str | None, flags: list[str]) -> list[str]:
    out = list(flags)
    if urgency == "critical" or flags:
        if "hitl_locked" not in out:
            out.append("hitl_locked")
    return out
