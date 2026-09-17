# Sneha — execution order 3 (parallel with Lakshmi)

**Concept:** LangChain / Gemini grounded generation  
**Owns:** in-depth SOAP **summary** from three inputs  
**Does not own:** recommendation bullets — that is **Lakshmi**

**Your three inputs**

1. `patient_data` from Radhakrishna (`extract_patient_data`)
2. `medical_data` from Vinayak (`extract_medical_data`)
3. `retrieved_docs` from Vamsi (`retrieve_guidelines`)

Read [CONTRACTS.md](CONTRACTS.md). You may start as soon as that file exists, using **mock JSON**. Do not wait for live Gemini or the UI.

---

## Your sequence

| Your order | Global phase | What |
| ---: | --- | --- |
| SN1 | Phase 3 | Prompt + `SummaryDraft` |
| SN2 | Phase 3 | LangChain / Gemini SOAP writer |
| SN3 | Phase 3 | In-depth structure (still grounded) |
| SN4 | Phase 3 | Mock writer |
| SN5 | Phase 3 | Tests + CLI |

Turjoy calls you **after** extract + RAG join, then calls Lakshmi separately.

---

## AI task (yours)

Use **LangChain + Gemini** (when keys exist) to write an **in-depth educational SOAP summary** that:

- Uses **only** facts from the three inputs
- Starts with `Educational prototype. Not for clinical use.`
- Is longer than a one-liner (this is the in-depth requirement)
- Names evidence topics from `retrieved_docs` under an Evidence used heading
- Never invents a lab, medication, or diagnosis
- Does **not** emit a recommendations list (Lakshmi)

If medical_data has HbA1c 9.2, the summary must mention 9.2.

---

## Prompt SN1 — function + prompt file

```
Implement backend/app/summarize/summary.py owned by Sneha.

from app.contracts import PatientData, MedicalData, RetrievedDoc, SummaryDraft

def create_indepth_summary(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> SummaryDraft:
    ...

System prompt must require:
- not-for-clinical-use first line
- only facts from the three inputs
- if a field is missing, say it is not documented — do not guess
- do not output recommendations, orders, or a citations array of follow-ups
- used_topics = retrieved doc topics actually mentioned

Do not call retrieve_guidelines or extract_*. You receive the three objects already built.
Do not implement create_recommendations. Lakshmi owns that.
```

---

## Prompt SN2 — LangChain / Gemini generation

```
When MOCK_LLM=false and GEMINI_API_KEY or OPENAI_API_KEY is set, use LangChain.

User payload, clearly separated:

PATIENT_JSON: ...
MEDICAL_JSON: ...
EVIDENCE_CHUNKS: list of {title, topic, text, citation}

Ask for JSON matching SummaryDraft (disclaimer, summary, used_topics).
Parse strictly; drop extra keys.
Temperature low. If the model adds a Plan that invents a drug not in medical_data, strip it in post-processing.
```

---

## Prompt SN3 — in-depth structure

```
The summary string should include markdown headings:
## Subjective
## Objective
## Assessment
## Plan
## Evidence used

Subjective: chief concern + history facts from medical_data; mention patient age/setting from patient_data if present.
Objective: vitals and labs from medical_data (include 9.2 for CR-001).
Assessment: only problems already listed.
Plan: restates the note's plan; do not add new orders.
Evidence used: retrieved topic titles only.

Keep under ~600 words so Adarsh's HITL drawer stays readable, but not a 3-sentence stub.
```

---

## Prompt SN4 — mock writer (required)

```
backend/app/summarize/summary_heuristics.py builds SummaryDraft without an LLM.

Rules:
- Always include the disclaimer
- Mention patient name/age if present
- Mention each problem and each lab value from medical_data
- List retrieved doc titles under Evidence used
- CR-001 mock must contain "diabetes" and "9.2"

MOCK_LLM=true uses this path. Live path falls back here on errors.
```

---

## Prompt SN5 — tests + CLI

```
backend/tests/test_summarize.py using fixture JSON (no network):

- CR-001-like patient + medical + diabetes RetrievedDoc
  → summary mentions diabetes and 9.2
  → does not mention sepsis if sepsis was not in inputs
- Does not mention problems that were not in medical_data
- Return type is SummaryDraft, not a recommendations list

CLI: python -m app.summarize.summary path/to/patient.json path/to/medical.json path/to/docs.json
Print the summary markdown. Demo without the UI.
```

---

## Handoff

Turjoy imports `create_indepth_summary` in the summary node.  
Adarsh renders `draft.summary` in the HITL drawer.  
Lakshmi does not rewrite your SOAP; she only adds recs.
