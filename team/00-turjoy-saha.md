# Turjoy Saha — execution order 0, 4, 6

**Concepts:** HITL, LangGraph multi-agent orchestration, LLM fallback  
**You own extra work** because you are coordinating the rebuild. Adarsh still owns the visible UI, REST routes, and the run database. You own everything that *makes the agents pause, recover, and stay safe*.

Read [CONTRACTS.md](CONTRACTS.md) before Prompt T0.

---

## Your sequence vs the team

| Your order | Global phase | What you do | Team can do in parallel |
| ---: | --- | --- | --- |
| T0–T4 | **0 — you go first** | Repo, contracts code, synthetic notes, LLM provider, graph skeleton | nobody codes yet |
| — | 1–3 | Review PRs only | Adarsh, Siva, Vamsi, Radhakrishna, Vinayak, Sneha, Lakshmi |
| T5–T8 | **4 — after teammate functions exist** | Wire extract + RAG + summarize, HITL interrupt, safety | Adarsh starts HITL UI against your API |
| T9–T12 | **6 — last** | Observability, memory chat, tests, Docker, demo script | Adarsh polishes UI |

If teammates are not ready after T4, keep going with **stubs** that return the golden CR-001 JSON from CONTRACTS.md.

---

## AI task (yours)

Ship a **LangGraph `StateGraph`** that:

1. Ingests a note
2. Routes specialty + urgency
3. Fans out analysis / labs / RAG in parallel (call teammate functions)
4. Joins → Sneha summary → Lakshmi recommendations → safety
5. **`interrupt_before=["hitl_review"]`** so nothing is released until Approve / Edit / Reject
6. Falls back **OpenAI → Gemini → mock** and still completes the graph

That is the capstone differentiator. Do not leave HITL as a fake button that never pauses the graph.

---

## Prompt T0 — empty repo skeleton

Paste into Cursor in the **new empty repo**:

```
You are scaffolding an educational clinical-report assistant. NOT for clinical use. Synthetic data only.

Create this exact layout and a root README that says the product is an educational prototype:

backend/app/{__init__.py,config.py,contracts.py,main.py}
backend/app/api/__init__.py
backend/app/extract/{__init__.py,patient.py,medical.py}
backend/app/rag/{__init__.py,ingest.py,retrieve.py}
backend/app/summarize/{__init__.py,summary.py,recommend.py}
backend/app/graph/{__init__.py,state.py,workflow.py}
backend/app/llm/__init__.py
backend/app/memory/__init__.py
backend/app/logging/__init__.py
backend/app/agents/__init__.py
backend/tests/conftest.py
frontend/  (Vite + React + TypeScript + Tailwind placeholder App.tsx with a red disclaimer banner)
data/reports/ data/labs/ data/guidelines/ data/expected/
scripts/
.env.example  (MOCK_LLM=true, OPENAI_API_KEY=, GEMINI_API_KEY=, ENABLE_PUBMED=false, ENABLE_OPENFDA=false)
.gitignore
backend/requirements.txt  (fastapi, uvicorn, pydantic, langgraph, langchain, langchain-openai, langchain-google-genai, chromadb, pypdf, tenacity, pytest, python-dotenv, sse-starlette)
docker-compose.yml stub

Put the Pydantic models from team/CONTRACTS.md into backend/app/contracts.py unchanged.

Do not implement agents yet. Stub workflow.py with a function build_graph() that raises NotImplementedError.
Add a FastAPI app in main.py that only serves GET /api/health returning {status:ok, disclaimer, mock_llm:true}.

Commit-quality code, no PHI, no copyrighted guidelines.
```

**Done when:** `uvicorn` serves `/api/health` and `contracts.py` matches the team file.

---

## Prompt T1 — synthetic case library (dummy patients)

```
Create synthetic educational cases under data/. Invented identities only. Prefix MRNs with SYN-.

Add data/cases.json listing at least these IDs with title, specialty, urgency, report_path, lab_path:

CR-001 endocrine routine — T2DM clinic, HbA1c 9.2%, metformin (happy path)
CR-002 cardio critical — BP 178/110, missed amlodipine
CR-003 infectious_disease critical — suspected sepsis, lactate 4.2
CR-004 heme routine — iron deficiency, Hb 8.1
CR-005 general routine — normal annual physical (negative control)
CR-006 cardio routine — HFrEF, BNP 980
CR-007 renal routine — AKI on CKD, eGFR 28
CR-008 cardio critical — chest pain, troponin 0.18
CR-009 endocrine routine — hypothyroidism, TSH 18
CR-010 general routine — DM + HTN + CKD
CR-011 — garbled/unreadable scan text so ingest can fail closed
CR-012 general routine — warfarin + amiodarone + simvastatin

For each, write a markdown clinic note in data/reports/CR-00X.md and matching labs JSON in data/labs/.
Every note must start with: Educational prototype. Not for clinical use. Synthetic patient.

Also write data/expected/CR-001.json, CR-003.json, CR-005.json, CR-011.json with must_mention / guideline_topics / critical flags so pytest can use them later.

Do not copy copyrighted NICE/UpToDate text. Keep notes short (under 400 words).
```

**Done when:** teammates can open `data/reports/CR-001.md` and see HbA1c 9.2.

---

## Prompt T2 — LLM provider (OpenAI → Gemini → mock)

```
Implement backend/app/llm/provider.py.

Settings from env:
- MOCK_LLM=true means never call a network LLM.
- If MOCK_LLM=false, try OpenAI (gpt-4o-mini) first, then Gemini, then mock.
- Use tenacity: 3 retries, exponential backoff, then fall over to the next provider.

Export:
- complete_text(system: str, user: str, mock: str) -> object with .text .tokens .model .provider
- complete_json(system: str, user: str, mock: dict) -> same, .text is JSON string

Mock path must return the provided mock argument (json.dumps for complete_json).
Never log API keys. If a call fails, set fallback=True on the result.

Add backend/tests/test_fallback.py: simulate OpenAI 429 and assert Gemini (or mock) is used.
Add backend/tests/conftest.py that forces MOCK_LLM=true.
```

**Done when:** `pytest backend/tests/test_fallback.py` passes with no keys.

---

## Prompt T3 — graph state + skeleton nodes

```
Implement GraphState TypedDict in backend/app/graph/state.py with fields from a clinical pipeline:
thread_id, case_id, raw_text, extracted_text, specialty, urgency, analysis, lab_flags,
retrieved_docs, summary, recommendations, citations, safety_flags, hitl_required,
human_decision, human_edits, human_feedback, chat_history, errors, events, status, ingest_error.

analysis should be a dict that can hold patient_data and medical_data dumps.

Implement append_event(agent, decision, **metrics) helper.

In workflow.py create a StateGraph with nodes that currently return stubs:
ingest → router → fanout(analysis, labs, rag) → synthesize → summary → recommendation → safety → hitl_review → finalize
urgent branch: router --critical--> urgent_safety → same fanout

Use langgraph MemorySaver checkpointer.
Do not add interrupt_before yet (that's T6).
Each stub node must append an event so the UI timeline will work.

Ingest: if text looks garbled (very few vowels / 'UNREADABLE'), set ingest_error and status ingest_failed.
Router: keyword heuristics for endocrine/cardio/infectious_disease/renal/heme/general and routine vs critical (sepsis, troponin, BP>=180, lactate).
```

**Done when:** importing `build_graph()` does not crash.

---

## Prompt T4 — publish stub functions so teammates are unblocked

```
Create stub implementations that match team/CONTRACTS.md exactly so other branches can import them. One function per owner:

backend/app/extract/patient.py     → extract_patient_data          # Radhakrishna
backend/app/extract/medical.py     → extract_medical_data          # Vinayak
backend/app/rag/ingest.py          → ingest_guideline_corpus, list_guideline_chunks  # Siva
backend/app/rag/retrieve.py        → embed_guidelines, retrieve_guidelines           # Vamsi
backend/app/summarize/summary.py   → create_indepth_summary        # Sneha
backend/app/summarize/recommend.py → create_recommendations        # Lakshmi

Stubs may use heuristics on CR-001 (diabetes, 9.2) but must return valid Pydantic models.
Add a one-line comment: "Replace stub — owned by <person>".

Do not delete these files later; each teammate overwrites only their function bodies.
```

**Stop here and tell every named person to start their own README.**

---

## Prompt T5 — wire teammate functions into agents

Run after extract / RAG / summarize PRs exist (or keep stubs).

```
Replace stub agent nodes with real calls. Do not merge teammate files.

- analysis node: call extract_patient_data AND extract_medical_data separately
  store state["analysis"] = {"patient": patient.model_dump(), "medical": medical.model_dump()}
- rag node: query from problems + labs; retrieved_docs = retrieve_guidelines(query, specialty)
- summary node: draft = create_indepth_summary(patient, medical, retrieved_docs)  # Sneha
- recommendation node: recs = create_recommendations(patient, medical, retrieved_docs)  # Lakshmi
  write draft.summary, recs, flattened citations onto state
- labs node: copy medical.labs into lab_flags

Keep mock LLM path working. Add backend/tests/test_graph.py:
- CR-001 reaches awaiting_review, summary contains diabetes and 9.2, retrieved topic includes diabetes
- parallel events include analysis, labs, rag
```

---

## Prompt T6 — HITL interrupt (required)

```
This is the HITL requirement. Use LangGraph interrupt_before=["hitl_review"].

When the graph hits hitl_review, it MUST pause with status awaiting_review.
Nothing is finalized until a human decision is applied via a resume API.

Implement in graph + a service Adarsh can call:

def start_run(text, case_id=None) -> run_id
def get_state(run_id)
def apply_review(run_id, decision: approve|edit|reject, edits="", feedback="") 

Behavior:
- approve → finalize → status finalized
- edit → replace recommendation detail with edits, status approved_with_edits, then finalize
- reject → revise node regenerates a more conservative summary using feedback, then safety, then interrupt HITL again
- critical urgency: hitl_required True always; there is no skip flag

Persist enough state that if the process restarts, apply_review can still finalize from a saved draft (JSON files under backend/.runs/ is OK).

Add tests: interrupt happens; approve yields finalized; reject does not finalize on the first pass.
```

---

## Prompt T7 — safety agent + fail-closed ingest

```
Add safety_node and urgent_safety_node.

Safety flags examples: critical_labs, possible_sepsis, acs_symptoms, hitl_locked.
Critical cases cannot skip HITL.
Recommendations must stay draft language ("discuss with clinician"), never auto-order meds or imaging.

Ingest fail-closed: CR-011 or empty PDF text → do not route, return recovery copy: "Paste the note as text."

Add tests/test_ingest.py for garbled input.
```

---

## Prompt T8 — router quality (cheap before expensive)

```
Improve router_node:
- keyword / heuristic scoring first
- optional complete_json when MOCK_LLM=false
- low confidence → general medicine
- wellness phrases (annual physical, preventive visit) stay general + routine
- negated phrases ("no chest pain") must not fire ACS

Tests/test_router.py:
- sepsis note → critical + infectious_disease
- chest pain / troponin → critical + cardio
- wellness → routine + general
- diabetes clinic → endocrine + routine
```

---

## Prompt T9 — follow-up Q&A from case memory

```
After status==finalized, POST /api/runs/{id}/chat answers questions using ONLY
extracted_text, analysis, summary, lab_flags already on the run. No new ingest.

Example: "what was the A1c?" for CR-001 must return 9.2.

Keep chat_history on the run. Mock path is keyword/heuristic over state.
```

---

## Prompt T10 — observability

```
Every node logs JSONL events: agent, decision, latency_ms, tokens, model, tool_calls, error.
Expose GET /api/metrics with counts, p50/p95 latency by agent, HITL mix (approve/edit/reject), model path (mock/openai/gemini), fallback count.

Create frontend/src/pages/Observability.tsx (Adarsh can restyle later) that fetches /api/metrics.
This page is yours; the rest of the UI is Adarsh's.
```

---

## Prompt T11 — pytest suite

```
From backend/, pytest must pass with MOCK_LLM=true and no network:

test_router, test_ingest, test_graph (CR-001, CR-003, CR-005, memory follow-up),
test_fallback, test_retry if PDF extract exists.

Graph test must prove fan-out (analysis, labs, rag events) and HITL interrupt.
Do not add live-LLM tests to default CI.
```

---

## Prompt T12 — Docker + demo script

```
Finish docker-compose.yml for backend (8000) and frontend (5173).
Write a "Manual demo script" section into the root README:

1. Library → CR-001 → timeline shows fanout → Approve
2. Follow-up: what was the A1c? → 9.2 from memory
3. CR-003 critical → HITL required
4. Observability page
5. CR-011 ingest fail-closed

Confirm .env.example documents MOCK_LLM, keys, and the not-for-clinical-use disclaimer.
```

---

## Extra stretch (only if time)

Paste one at a time:

```
Add PDF ingest with pypdf, 3 retries on OSError, PdfExtractError on empty text.
Script scripts/generate_lab_pdfs.py so CR-001 can be uploaded as a file.
```

```
Optional hybrid: if OPENAI_API_KEY is set, Vamsi's embed path should run at reindex. Do not implement retrieve yourself — call retrieve_guidelines from Vamsi and ingest_guideline_corpus from Siva.
```

---

## Handoff

| You produce | Who consumes |
| --- | --- |
| `data/reports/*`, `data/cases.json` | everyone |
| `build_graph`, `start_run`, `apply_review` | Adarsh |
| `/api/metrics`, Observability page | demo |
| stub → real wiring of all six teammate functions | whole pipeline |
