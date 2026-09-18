# Team playbook — rebuild this product on a new repo

Copy the whole `team/` folder into the empty repo. Each person opens **their** README and pastes prompts into Cursor **in the numbered order**. Do not start a later prompt until the previous one in your file is done.

`/` in the original assignment table meant **two people**. They do **not** share a backlog. Each person has a separate file, a separate public function, and a separate AI task.

**Not for clinical use.** Synthetic patients only.

---

## Who does what (one person each)

| Person | Concept | Owns | AI work they personally ship |
| --- | --- | --- | --- |
| **Turjoy Saha** (extra load) | HITL + multi-agent orchestration | Repo bootstrap, LangGraph, HITL interrupt, safety, LLM fallback, observability, integration, Docker, tests | LangGraph with `interrupt_before` HITL; OpenAI → Gemini → mock |
| **Adarsh** | HITL (UI + API + DB) | FastAPI, persistence, React app | Clinician Approve / Edit / Reject, SSE timeline, run store |
| **Siva** | RAG corpus | `data/guidelines/`, chunking, lexical index | Original educational cards + `ingest_guideline_corpus()` / `list_guideline_chunks()` |
| **Vamsi** | RAG retrieve | Embeddings DB + ranking | Chroma (when keyed) + `retrieve_guidelines()` |
| **Radhakrishna** | LangChain / Gemini | Patient variable only | `extract_patient_data()` → `PatientData` |
| **Vinayak** | LangChain / Gemini | Medical variable only | `extract_medical_data()` → `MedicalData` |
| **Sneha** | LangChain / Gemini | In-depth SOAP summary | `create_indepth_summary(patient, medical, retrieved_docs)` |
| **Lakshmi** | LangChain / Gemini | Cited recommendations | `create_recommendations(patient, medical, retrieved_docs)` |

---

## Execution order (whole team)

```
Phase 0  Turjoy        Bootstrap empty repo + contracts + synthetic notes
Phase 1  PARALLEL      Siva: guideline cards + lexical ingest
                       Radhakrishna: patient extractor
                       Vinayak: medical extractor
                       Adarsh: API skeleton + UI shell + run DB
Phase 2  Vamsi         Embed Siva's chunks + retrieve_guidelines()
Phase 3  PARALLEL      Sneha: SOAP summary from 3 inputs (mocks OK)
                       Lakshmi: cited recs from 3 inputs (mocks OK)
Phase 4  Turjoy        Wire all six functions + HITL + safety
Phase 5  Adarsh        Hook UI to real runs, HITL drawer, SSE
Phase 6  Turjoy        Observability, follow-up chat, pytest, Docker, demo
```

| Order | Person | Start after | Finish before |
| ---: | --- | --- | --- |
| 0 | Turjoy Saha | empty repo | anyone else writes code |
| 1 | Siva | order 0 | Vamsi embed |
| 1 | Radhakrishna | order 0 | Turjoy analysis node |
| 1 | Vinayak | order 0 | Turjoy analysis node |
| 1 | Adarsh (API/UI shell) | order 0 | Phase 5 |
| 2 | Vamsi | Siva chunks exist (or use a tiny fixture) | Turjoy RAG node |
| 3 | Sneha | contracts exist (mocks OK) | Turjoy summary node |
| 3 | Lakshmi | contracts exist (mocks OK) | Turjoy recommendation node |
| 4 | Turjoy Saha | teammate functions **or** stubs | Adarsh HITL UI |
| 5 | Adarsh (HITL UI + SSE) | `/api/runs` returns `awaiting_review` | demo |
| 6 | Turjoy Saha | UI can approve a run | presentation |

Sneha and Lakshmi do **not** wait for live Gemini. They implement against mock JSON in `CONTRACTS.md` first.

Vamsi does **not** write guideline markdown. Siva does **not** implement `retrieve_guidelines`. Radhakrishna does **not** fill labs. Vinayak does **not** fill name/MRN.

---

## How to use the prompts

1. Create a **new empty git repo**.
2. Paste `team/` into it (this folder).
3. Turjoy runs every prompt in [00-turjoy-saha.md](00-turjoy-saha.md) **T0 → T4** first.
4. Everyone else opens **only their file** and runs prompts top to bottom.
5. After each prompt, commit on a branch named `person/short-topic`.
6. Turjoy merges when that person's public function in `CONTRACTS.md` exists.

**Prompt rule:** paste the prompt as-is, then attach `team/CONTRACTS.md`. If Cursor invents extra folders, tell it: *keep the folder map in CONTRACTS.md*. *Do not implement a teammate's function.*

---

## Per-person files

| File | Person |
| --- | --- |
| [CONTRACTS.md](CONTRACTS.md) | Everyone — freeze this first |
| [00-turjoy-saha.md](00-turjoy-saha.md) | Turjoy Saha |
| [01-adarsh.md](01-adarsh.md) | Adarsh |
| [02-siva.md](02-siva.md) | Siva |
| [03-vamsi.md](03-vamsi.md) | Vamsi |
| [04-radhakrishna.md](04-radhakrishna.md) | Radhakrishna |
| [05-vinayak.md](05-vinayak.md) | Vinayak |
| [06-sneha.md](06-sneha.md) | Sneha |
| [07-lakshmi.md](07-lakshmi.md) | Lakshmi |

---

## Merge checklist (demo day)

- [x] `MOCK_LLM=true` full path works with no API keys
- [x] CR-001: Sneha's summary mentions diabetes and 9.2; Vamsi's RAG topic is diabetes
- [x] Lakshmi's recommendations each have a citation from retrieved docs
- [x] CR-003 (sepsis-style): HITL cannot be skipped
- [x] Unreadable PDF: ingest fails closed, UI asks for pasted text
- [x] Approve / Edit / Reject all persist on refresh
- [x] Banner: Not for clinical use
