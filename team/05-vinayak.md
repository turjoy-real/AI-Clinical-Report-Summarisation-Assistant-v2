# Vinayak — execution order 1 (parallel with Radhakrishna)

**Concept:** LangChain / Gemini structured extraction  
**Owns:** `extract_medical_data()` → **medical details only**  
**Does not own:** name, age, MRN, sex — that is **Radhakrishna**

Read [CONTRACTS.md](CONTRACTS.md). Start after Turjoy **T0 + T1** so `data/reports/CR-001.md` exists.

You and Radhakrishna run in parallel on the **same note**, but you return different variables. Do not put demographics on `MedicalData`.

---

## Your sequence

| Your order | Global phase | What |
| ---: | --- | --- |
| VY1 | Phase 1 | Function skeleton + MedicalData / LabFlag |
| VY2 | Phase 1 | LangChain / Gemini extract |
| VY3 | Phase 1 | Heuristic mock for CR-001 labs and problems |
| VY4 | Phase 1 | CLI demo |
| VY5 | Phase 1 | Tests |

---

## AI task (yours)

Use **LangChain + Gemini** (when `GEMINI_API_KEY` is set) to extract **only** `MedicalData`: chief_concern, problems, medications, allergies, vitals, labs, assessment, plan, missing_sections.

- Do **not** copy the patient name into `problems`
- Labs become `LabFlag` rows (analyte, value, unit, flag if obvious else `unknown`)
- When `MOCK_LLM=true` or Gemini fails, heuristics must still parse CR-001 (diabetes, HbA1c 9.2, metformin)
- Unreadable notes: `missing_sections` includes `unreadable_source`, problems stay empty, no crash

---

## Prompt VY1 — skeleton

```
Implement backend/app/extract/medical.py owned by Vinayak.

from app.contracts import MedicalData, LabFlag

def extract_medical_data(document_text: str) -> MedicalData:
    ...

If document_text is empty, return MedicalData() defaults, do not raise.
Do not import or call extract_patient_data. Radhakrishna owns that file.
Add backend/app/extract/medical_prompt.py — educational, not clinical use, JSON only, extract only facts in the note, no invented diagnoses, no demographics.
```

---

## Prompt VY2 — LangChain / Gemini path

```
Use LangChain with a structured-output or JSON parser against Gemini.

Env:
- MOCK_LLM=true → never call Gemini
- MOCK_LLM=false and GEMINI_API_KEY set → Gemini extract
- On timeout/error → fall back to heuristics

System prompt:
- Educational prototype, not for clinical use
- Extract chief concern, problems, medications, allergies, vitals, labs, assessment, plan
- Never infer a diagnosis that is not written
- Labs: analyte, value, unit, flag
- Temperature 0
```

---

## Prompt VY3 — heuristic mock (required)

```
backend/app/extract/medical_heuristics.py parses CR-001 without an LLM:
- problems includes type 2 diabetes / diabetes
- medications includes metformin
- labs include HbA1c with value 9.2
- chief_concern from that section if present
- assessment/plan from those headings if present

Use this when MOCK_LLM=true and as Gemini fallback.
```

---

## Prompt VY4 — CLI

```
python -m app.extract.medical data/reports/CR-001.md
prints one JSON object labeled MEDICAL.
This is how you demo your part without the UI.
Do not print name or MRN.
```

---

## Prompt VY5 — tests

```
backend/tests/test_extract_medical.py:

- CR-001: problems mention diabetes; a lab analyte matches hba1c/a1c; value contains 9.2; medications mention metformin
- medical.problems must not be a patient name
- CR-005 wellness: does not crash; no requirement for critical_high
- CR-011: missing_sections nonempty; does not crash
- return type is MedicalData
```

---

## Handoff

Write `data/expected/medical-CR-001.json` from your CLI.  
Tell **Sneha** and **Lakshmi** this file is input 2 of 3.  
Tell **Turjoy** analysis node calls `extract_medical_data` for the medical half, and labs node can copy `medical.labs`.
