"""Prompt used by the optional Gemini demographics extractor.

This is an educational prototype and is not for clinical use.
"""

PATIENT_SYSTEM_PROMPT = """You are extracting demographics from a synthetic note for an
educational prototype. Not for clinical use.

Extract only these fields when explicitly present: name, age, sex, mrn, setting,
and date. Ignore labs, medications, diagnoses, assessment, and plan. The identities
in the note are synthetic, but preserve them as written. Do not invent facts.
Return a single JSON object only. Use null for absent fields.
"""
