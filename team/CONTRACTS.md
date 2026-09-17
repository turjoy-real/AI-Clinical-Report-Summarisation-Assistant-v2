# Shared contracts (do not change without the whole team)

These types are the only glue between people. Implement against this file, not against each other's internal code.

**Rules**

- Synthetic data only. No real names, MRNs, or PHI.
- Every user-facing string and generated summary must include: `Educational prototype. Not for clinical use.`
- If a live LLM key is missing, your function still returns valid JSON using a heuristic/mock path.
- Do not invent labs, diagnoses, or guideline citations that are not in the inputs.
- One person owns one public function. Do not edit a teammate's file except via a requested PR review.

---

## Folders (new repo)

```
backend/app/contracts.py                 # Pydantic models (copy from this file)
backend/app/extract/patient.py           # Radhakrishna
backend/app/extract/medical.py           # Vinayak
backend/app/rag/ingest.py                # Siva
backend/app/rag/retrieve.py              # Vamsi
backend/app/summarize/summary.py         # Sneha
backend/app/summarize/recommend.py       # Lakshmi
backend/app/graph/                       # Turjoy — LangGraph + HITL
backend/app/api/                         # Adarsh — FastAPI
backend/app/memory/                      # Adarsh — run / case persistence
frontend/src/                           # Adarsh — UI (Turjoy: Observability page)
data/reports/                           # Turjoy — synthetic clinical notes
data/labs/                              # Turjoy — synthetic lab JSON
data/guidelines/                        # Siva — educational reference cards
data/chroma/                            # Vamsi — vector index (optional)
```

---

## 1. Patient data — Radhakrishna output

```python
from typing import Literal
from pydantic import BaseModel, Field

class PatientData(BaseModel):
    name: str = "synthetic-unknown"
    age: int | None = None
    sex: str | None = None
    mrn: str | None = None          # synthetic IDs only, e.g. SYN-1001
    setting: str | None = None      # clinic, ED, ward
    date: str | None = None
    source_case_id: str | None = None
```

---

## 2. Medical data — Vinayak output

```python
class LabFlag(BaseModel):
    analyte: str
    value: str
    unit: str = ""
    flag: Literal["normal", "high", "low", "critical_high", "critical_low", "unknown"] = "unknown"


class MedicalData(BaseModel):
    chief_concern: str = ""
    problems: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    vitals: dict[str, str] = Field(default_factory=dict)
    labs: list[LabFlag] = Field(default_factory=list)
    assessment: str = ""
    plan: str = ""
    missing_sections: list[str] = Field(default_factory=list)
```

---

## 3. RAG retrieved doc — Vamsi output (Siva supplies chunks)

```python
class GuidelineChunk(BaseModel):
    id: str
    title: str
    topic: str
    source: str
    text: str
    citation: str = ""


class RetrievedDoc(BaseModel):
    id: str
    title: str
    topic: str
    source: str                     # filename, e.g. diabetes.md
    text: str
    score: float = 0.0
    citation: str = ""              # public teaching source title, never a copyrighted PDF
```

---

## 4. Summary + recommendations — Sneha and Lakshmi

```python
class Recommendation(BaseModel):
    title: str
    detail: str
    citations: list[str] = Field(default_factory=list)


class SummaryDraft(BaseModel):
    disclaimer: str = "Educational prototype. Not for clinical use."
    summary: str                    # in-depth SOAP-style writeup (Sneha)
    used_topics: list[str] = Field(default_factory=list)


class SummaryBundle(BaseModel):
    """Turjoy joins Sneha + Lakshmi outputs onto graph state. Do not implement this join yourself."""
    disclaimer: str = "Educational prototype. Not for clinical use."
    summary: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    used_topics: list[str] = Field(default_factory=list)
```

---

## 5. Public functions — one owner each

```python
# backend/app/extract/patient.py  (Radhakrishna)
def extract_patient_data(document_text: str) -> PatientData:
    """Demographics / encounter only. No labs, problems, or medications."""


# backend/app/extract/medical.py  (Vinayak)
def extract_medical_data(document_text: str) -> MedicalData:
    """Clinical content only. No name, age, MRN, or sex."""


# backend/app/rag/ingest.py  (Siva)
def ingest_guideline_corpus(guidelines_dir: str) -> int:
    """Chunk original educational cards and write the lexical index. Return chunk count."""


def list_guideline_chunks() -> list[GuidelineChunk]:
    """Read chunks so Vamsi can embed them. Do not retrieve here."""


# backend/app/rag/retrieve.py  (Vamsi)
def embed_guidelines() -> int:
    """Embed Siva's chunks into Chroma when a key exists; no-op (return 0) without a key."""


def retrieve_guidelines(query: str, specialty: str | None = None, k: int = 4) -> list[RetrievedDoc]:
    """Return top-k educational guideline chunks for the query."""


# backend/app/summarize/summary.py  (Sneha)
def create_indepth_summary(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> SummaryDraft:
    """Grounded SOAP writeup from all three inputs. Do not emit recommendations."""


# backend/app/summarize/recommend.py  (Lakshmi)
def create_recommendations(
    patient_data: PatientData,
    medical_data: MedicalData,
    retrieved_docs: list[RetrievedDoc],
) -> list[Recommendation]:
    """Cited follow-up discussion points from all three inputs. Do not rewrite the SOAP summary."""
```

Turjoy calls Radhakrishna + Vinayak in the analysis node, Vamsi in the RAG node, Sneha then Lakshmi after the join.

---

## 6. HITL review payload (Adarsh UI ↔ Turjoy graph)

```python
class ReviewRequest(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    edits: str = ""
    feedback: str = ""
```

Statuses the API may return:

| status | meaning |
| --- | --- |
| `running` | graph in progress |
| `awaiting_review` | paused for clinician |
| `revising` | reject path, regenerating |
| `approved` / `approved_with_edits` | human signed off |
| `finalized` | released to follow-up chat |
| `ingest_failed` | unreadable file; ask for pasted text |

---

## 7. HTTP surface Adarsh owns, others consume

| Method | Path | Owner |
| --- | --- | --- |
| GET | `/api/health` | Adarsh |
| GET | `/api/cases` | Adarsh (data from Turjoy library) |
| POST | `/api/runs` | Adarsh (calls Turjoy graph) |
| GET | `/api/runs/{id}` | Adarsh |
| GET | `/api/runs/{id}/events` | Adarsh SSE |
| POST | `/api/runs/{id}/review` | Adarsh → Turjoy HITL resume |
| POST | `/api/runs/{id}/chat` | Turjoy Q&A, Adarsh exposes |
| GET | `/api/metrics` | Turjoy |
| POST | `/api/rag/reindex` | Adarsh route calls Siva ingest then Vamsi embed |

---

## 8. Golden fixture (everyone tests against this)

Use synthetic case `CR-001`: type 2 diabetes, HbA1c **9.2%**, metformin, endocrinology clinic.

- Radhakrishna: `name` / synthetic `mrn` present; **no** HbA1c in patient fields
- Vinayak: `problems` includes diabetes; labs include HbA1c 9.2; **no** patient name in problems
- Siva: diabetes.md exists and mentions HbA1c
- Vamsi: top hits include topic `diabetes`, not `sepsis`
- Sneha: summary mentions diabetes and 9.2
- Lakshmi: every recommendation has at least one citation title from retrieved docs
