# Lakshmi — execution order 3 (parallel with Sneha)

**Concept:** LangChain / Gemini grounded generation  
**Owns:** **cited recommendations** from the same three inputs  
**Does not own:** the SOAP summary — that is **Sneha**

**Your three inputs** (same as Sneha; you do not wait for her output)

1. `patient_data` from Radhakrishna
2. `medical_data` from Vinayak
3. `retrieved_docs` from Vamsi RAG

Read [CONTRACTS.md](CONTRACTS.md). You may start as soon as that file exists, using **mock JSON**.

---

## Your sequence

| Your order | Global phase | What |
| ---: | --- | --- |
| LK1 | Phase 3 | Function + Recommendation model |
| LK2 | Phase 3 | LangChain / Gemini recs |
| LK3 | Phase 3 | Citation lock (RAG titles only) |
| LK4 | Phase 3 | Mock path |
| LK5 | Phase 3 | Tests + CLI |

Turjoy calls you after Sneha (or in parallel after the join). You must not call Sneha's function.

---

## AI task (yours)

Use **LangChain + Gemini** (when keys exist) to produce **3–6 educational follow-up recommendations** that:

- Use **only** facts from the three inputs
- Each item has `title`, `detail`, and `citations`
- Every citation string is copied from `retrieved_docs[i].citation` or `.title`
- Language is draft-for-clinician, never an order ("discuss", "consider")
- If RAG is empty, say evidence was not retrieved — **no fake NICE titles**
- Critical-sounding medical_data (sepsis, troponin, `critical_high`) uses more urgent wording, still not orders

---

## Prompt LK1 — function + prompt file

```
Implement backend/app/summarize/recommend.py owned by Lakshmi.

from app.contracts import PatientData, MedicalData, RetrievedDoc, Recommendation

def create_recommendations(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> list[Recommendation]:
    ...

System prompt:
- Educational prototype, not for clinical use
- discussion points for a human clinician, not orders
- every recommendation lists citation strings copied from retrieved docs
- do not invent labs or drugs
- do not write a SOAP summary

Do not call create_indepth_summary. Sneha owns that.
Do not call retrieve_guidelines yourself.
```

---

## Prompt LK2 — LangChain / Gemini generation

```
When MOCK_LLM=false and a key is set, use LangChain.

User payload:

PATIENT_JSON
MEDICAL_JSON
EVIDENCE_CHUNKS: {title, topic, text, citation}

Ask for JSON list of Recommendation objects.
If the model cites a title that is not in retrieved_docs, strip that citation in post-processing.
If that leaves a rec with zero citations and docs were provided, attach the top-scoring doc title.
Temperature low.
```

---

## Prompt LK3 — citation + urgency rules

```
- 3–6 recommendations
- CR-001 + diabetes docs: at least one rec about glycemic follow-up / HbA1c, citing the diabetes card
- If medical_data has critical_high or problems suggesting sepsis/ACS, first rec should be "discuss immediately with a clinician" still without ordering tests
- Never recommend a medication that is not already in medical_data.medications unless the retrieved text explicitly discusses that class AND you frame it as teaching, not a prescription
- Patient name may appear in detail; do not leak extra identifiers
```

---

## Prompt LK4 — mock path (required)

```
backend/app/summarize/recommend_heuristics.py builds list[Recommendation] without an LLM.

Rules:
- For each retrieved doc, add a recommendation that quotes that doc's title as a citation
- Also mention any critical/high labs from medical_data
- If retrieved_docs is empty, return one rec: "Guideline evidence was not retrieved; clinician review required." with citations=[]
- Do not emit "NICE", "UpToDate", or other names that were not in the docs

MOCK_LLM=true uses this path. Live path falls back here on errors.
```

---

## Prompt LK5 — tests + CLI

```
backend/tests/test_recommend.py (no network):

- CR-001-like inputs + diabetes RetrievedDoc
  → every recommendation has len(citations) >= 1
  → citations are a subset of provided doc titles/citations
- Empty retrieved_docs → no invented guideline names like "NICE NG28"
- Return type is list[Recommendation], not a SOAP string

CLI: python -m app.summarize.recommend path/to/patient.json path/to/medical.json path/to/docs.json
Print JSON recs. Demo without the UI.
```

---

## Handoff

Turjoy writes your list onto `state["recommendations"]` and flattens citations.  
Adarsh shows them in the HITL drawer next to Sneha's summary.  
Sit in on the first Approve click to confirm the recs are yours, not a stub.
