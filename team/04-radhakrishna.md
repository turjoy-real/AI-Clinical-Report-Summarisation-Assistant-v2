# Radhakrishna — execution order 1 (parallel with Vinayak)

**Concept:** LangChain / Gemini structured extraction  
**Owns:** `extract_patient_data()` → **patient details only**  
**Does not own:** medical problems, labs, meds — that is **Vinayak**

Read [CONTRACTS.md](CONTRACTS.md). Start after Turjoy **T0 + T1** so `data/reports/CR-001.md` exists.

You and Vinayak run in parallel on the **same note**, but you return different variables. Do not merge his model into yours.

---

## Your sequence

| Your order | Global phase | What |
| ---: | --- | --- |
| RK1 | Phase 1 | Function skeleton + PatientData |
| RK2 | Phase 1 | LangChain / Gemini extract |
| RK3 | Phase 1 | Heuristic mock for CR-001 |
| RK4 | Phase 1 | CLI demo |
| RK5 | Phase 1 | Tests |

---

## AI task (yours)

Use **LangChain + Gemini** (when `GEMINI_API_KEY` is set) to extract **only** `PatientData`: name, age, sex, mrn, setting, date.

- Do **not** put HbA1c, metformin, or diagnoses into `PatientData`
- When `MOCK_LLM=true` or Gemini fails, heuristics must still fill CR-001 demographics
- Empty or unreadable notes: return defaults, do not raise

---

## Prompt RK1 — skeleton

```
Implement backend/app/extract/patient.py owned by Radhakrishna.

from app.contracts import PatientData

def extract_patient_data(document_text: str) -> PatientData:
    ...

If document_text is empty, return PatientData() defaults, do not raise.
Do not import or call extract_medical_data. Vinayak owns that file.
Add backend/app/extract/patient_prompt.py — educational, not clinical use, JSON only, no invented facts, demographics only.
```

---

## Prompt RK2 — LangChain / Gemini path

```
Use LangChain with a structured-output or JSON parser against Gemini.

Env:
- MOCK_LLM=true → never call Gemini
- MOCK_LLM=false and GEMINI_API_KEY set → Gemini extract
- On timeout/error → fall back to heuristics

System prompt:
- Educational prototype, not for clinical use
- Extract ONLY name, age, sex, MRN, setting, date present in the note
- Invented identities in the notes are synthetic; still extract them as written
- Ignore labs, meds, assessment, plan
- Temperature 0
```

---

## Prompt RK3 — heuristic mock (required)

```
backend/app/extract/patient_heuristics.py parses CR-001 without an LLM:
- name around "Patient:"
- age from "58-year-old" style phrases
- mrn SYN-#### if present
- setting from clinic/ED/ward wording
- date if present

Use this when MOCK_LLM=true and as Gemini fallback.
```

---

## Prompt RK4 — CLI

```
python -m app.extract.patient data/reports/CR-001.md
prints one JSON object labeled PATIENT.
This is how you demo your part without the UI.
Do not print medical fields.
```

---

## Prompt RK5 — tests

```
backend/tests/test_extract_patient.py:

- CR-001: name or mrn present; age is 58 if written
- patient JSON must not contain HbA1c, metformin, or diabetes as field values
- CR-011 unreadable: does not crash
- return type is PatientData

Do not assert on labs. That is Vinayak.
```

---

## Handoff

Write `data/expected/patient-CR-001.json` from your CLI.  
Tell **Sneha** and **Lakshmi** this file is input 1 of 3.  
Tell **Turjoy** analysis node calls `extract_patient_data` only for the patient half.
