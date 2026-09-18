"""Prompt text for the in-depth SOAP summary LLM path. Owned by Sneha."""

from __future__ import annotations

import json

from app.contracts import MedicalData, PatientData, RetrievedDoc

SYSTEM_PROMPT = """You are assisting an educational prototype. Not for clinical use.

You will be given synthetic patient demographics, synthetic clinical data, and a
list of retrieved educational guideline chunks. Write an in-depth SOAP-style
summary using ONLY facts present in those three inputs.

Rules:
- The summary must start with the exact line: "Educational prototype. Not for clinical use."
- Use markdown headings, in this order: ## Subjective, ## Objective, ## Assessment,
  ## Plan, ## Evidence used.
- If a field is missing or not present in the inputs, say it is not documented.
  Never guess, infer, or fabricate a name, age, lab, medication, or diagnosis.
- Do not output a recommendations list, new orders, or a citations array of
  follow-up actions. The Plan section only restates the plan already present
  in the inputs.
- Evidence used must list only the titles of guideline chunks that are actually
  relevant to the facts above; do not invent guideline titles.
- Keep the summary under roughly 600 words. It must be more than a one-line stub.

Return a single JSON object with exactly these keys:
{
  "disclaimer": "Educational prototype. Not for clinical use.",
  "summary": string (the full markdown SOAP writeup described above),
  "used_topics": string[] (topics from EVIDENCE_CHUNKS actually mentioned in the summary)
}

Output valid JSON only, no markdown fences, no commentary.
"""


def build_user_prompt(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> str:
    evidence_chunks = [
        {
            "title": doc.title,
            "topic": doc.topic,
            "text": doc.text,
            "citation": doc.citation,
        }
        for doc in retrieved_docs
    ]
    return (
        "PATIENT_JSON:\n"
        f"{json.dumps(patient_data.model_dump(), indent=2)}\n\n"
        "MEDICAL_JSON:\n"
        f"{json.dumps(medical_data.model_dump(), indent=2)}\n\n"
        "EVIDENCE_CHUNKS:\n"
        f"{json.dumps(evidence_chunks, indent=2)}\n\n"
        "Return the JSON object now."
    )
