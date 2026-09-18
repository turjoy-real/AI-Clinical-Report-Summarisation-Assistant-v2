# AI Clinical Report Summarisation Assistant

Educational multi-agent prototype for the UST Enterprise Capstone (Healthcare). A clinician uploads a **synthetic** report. LangGraph agents extract findings, retrieve educational guidelines, draft a SOAP summary, then **pause for human approval** before anything is released.

**Not for clinical use.** All patients, labs, and recommendations are synthetic. The UI banner, API, and generated text repeat that disclaimer.

## Quick start

```bash
cd backend
python3 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
python ../scripts/ingest_rag.py
uvicorn app.main:app --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health).

**Ports:** backend `8000` (FastAPI/uvicorn), frontend `5173` (Vite proxies `/api` to `127.0.0.1:8000`).

`MOCK_LLM=true` (default) completes the full path with no API keys.

Docker:

```bash
cp .env.example .env
docker compose up --build
```

## Manual demo script

1. **Library → CR-001.** Timeline shows `fanout` then analysis, labs, and RAG. Approve the draft.
2. **Follow-up:** `what was the A1c?` — answer comes from case memory (`9.2`), not a new ingest.
3. **CR-003.** Router takes `critical` / infectious disease; safety flags fire; HITL cannot be skipped.
4. **Observability.** Show model path (`mock` / `openai` / `gemini`), latency, HITL mix.
5. **CR-011.** Ingest fails closed and asks the clinician to paste text.

## Who owns what

| Person | Public function / surface |
| --- | --- |
| **Turjoy** | LangGraph + HITL interrupt, LLM fallback, safety, chat, metrics, Docker |
| **Adarsh** | FastAPI, run store, React UI, HITL drawer, SSE |
| **Siva** | `ingest_guideline_corpus` / `list_guideline_chunks` |
| **Vamsi** | `embed_guidelines` / `retrieve_guidelines` |
| **Radhakrishna** | `extract_patient_data` |
| **Vinayak** | `extract_medical_data` |
| **Sneha** | `create_indepth_summary` |
| **Lakshmi** | `create_recommendations` |

Contracts: `team/CONTRACTS.md`.

## Architecture

```
Upload / case library
        │
        ▼
   Ingest  ──unreadable──► END (paste the note as text)
        │
        ▼
   Router ──critical──► Urgent safety gate
        │                            │
        └──routine───────────────────┤
                                     ▼
                              Parallel fan-out
                     ┌───────────────┼───────────────┐
                     ▼               ▼               ▼
               Analysis           Labs            Guideline RAG
                     └───────────────┼───────────────┘
                                     ▼
                          Sneha summary → Lakshmi recs → Safety
                                     │
                                     ▼
                          HITL interrupt (required)
                          Approve / Edit ──► Finalize ──► Follow-up Q&A
                          Reject ──► Revise ──► Safety ──► HITL again
```

LLM path: **OpenAI → Gemini → mock**. HITL uses LangGraph `interrupt_before=["hitl_review"]`.

## Tests

```bash
cd backend && python -m pytest
cd frontend && npm test
```

Default CI is mock-only (`MOCK_LLM=true`). Do not add live-LLM tests to the default suite.
