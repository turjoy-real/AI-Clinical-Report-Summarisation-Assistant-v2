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

## Manual test and demo

Use **mock LLM** (`MOCK_LLM=true`, the default). No API keys. About 8 minutes for the full path.

**Disclaimer first:** the red banner must say the product is an educational prototype and **not for clinical use**. Every synthetic note starts with the same line.

### 0. Confirm the app is up

1. Open [http://localhost:5173](http://localhost:5173).
2. Header should show **Inbox** and **Observability**.
3. Top-right should read **backend live · mock LLM** (amber dot). If it says **backend unreachable**, start uvicorn on port `8000` first.
4. Optional: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) should return `"status":"ok"`.

The home page has three blocks: **Inbox** (prior runs), **Upload or paste a report**, then **Synthetic case library**.

### 1. Happy path — CR-001 diabetes (must demo)

1. Scroll to **Synthetic case library**.
2. Open **CR-001** — “Type 2 diabetes clinic follow-up” / routine / HbA1c 9.2%.
3. Click **Start**. The workspace URL becomes `/workspace/<run_id>`.
4. Wait until status is **`awaiting_review`** (amber). Agents work for a few seconds.
5. **Left column — Agent timeline.** You should see ingest → router → a **fan-out** (`analysis`, `labs`, `rag`) → summary → recommendation → safety → HITL pause. Specialty should be **endocrine**, urgency **routine**.
6. **Source note** should include Jordan Hale (synthetic) and **HbA1c 9.2**.
7. **Guidelines retrieved** should mention diabetes.
8. **Abnormal findings** should list A1c / glucose-style labs.
9. **Clinician review required** drawer is open. Draft summary mentions diabetes and 9.2. Follow-up chat still says “Available after approval.”
10. Click **Approve**.
11. Status becomes **`finalized`** (green). **Released draft** appears. Chat unlocks.

### 2. Case-memory follow-up (not a new ingest)

1. Stay on the same finalized CR-001 run. Do **not** start a new case.
2. In **Follow-up chat**, type `what was the A1c?` and send.
3. The answer must include **`9.2`**. It is read from stored case memory (`extracted_text` / labs / summary), not a second pipeline run.
4. Ask `what medication is the patient on?` — expect **metformin**.

### 3. Critical HITL lock — CR-003 sepsis

1. Nav **Inbox** → start **CR-003** (“Suspected sepsis and pneumonia”).
2. Router should set **infectious_disease** + **critical** (red urgency).
3. Safety flags should include things like `possible_sepsis`, `critical_labs`, `hitl_locked`.
4. Graph **must** stop at **`awaiting_review`**. There is no skip.
5. Click **Reject**. In the feedback box type `too aggressive — keep draft language only` → **Send feedback**.
6. Status goes **`revising`**, then **`awaiting_review` again**. It is **not** finalized after the first reject.
7. Click **Approve** so the run can finish (or leave it pending to show the lock).

### 4. Fail-closed ingest — CR-011 garbled scan

1. Inbox → start **CR-011** (“Garbled scan”).
2. Status is **`ingest_failed`** (red). Copy says the document could not be read and to **paste the note as text**.
3. Timeline should **not** show router / fan-out / summary.
4. Recovery: on that same workspace, paste any readable synthetic line (for example the first paragraph of `data/reports/CR-001.md`) into **Pasted note text** → **Run assistant**. A new run should reach `awaiting_review`.

### 5. Home upload / paste (Inbox, not Workspace)

1. Inbox → **Upload or paste a report**.
2. **Run assistant** stays disabled until there is text or a file.
3. Paste:

   ```
   Educational prototype. Not for clinical use. Synthetic patient.
   Clinic follow-up for type 2 diabetes. HbA1c 9.2% on metformin.
   ```

4. Click **Run assistant**. A workspace run starts the same way as a library case.
5. Optional: **Document upload** accepts `.md` / `.txt` / `.pdf`. Use `data/reports/CR-001.md`.

### 6. Observability

1. After the runs above, open **Observability**.
2. **Runs total** should be > 0. **HITL mix** should show approve (and reject if you did CR-003).
3. **Model path** should be **`mock`** in this demo.
4. Latency table lists agents (`ingest`, `router`, `analysis`, `labs`, `rag`, `summary`, `recommendation`, `safety`).

### 7. Inbox worklist

1. Return to **Inbox**. Prior runs appear as a table (urgency, case, status, source, age).
2. Filter **Critical** — CR-003 should remain.
3. Filter **Ingest failed** — CR-011 should remain.
4. Click a row to reopen that workspace. Refresh the page: the same run, draft, and events reload from the store (no second run).

### Optional extras if there is time

| What | How | Expect |
| --- | --- | --- |
| Save edits | On any `awaiting_review` run: **Save edits** → rewrite a recommendation → **Submit edited plan** | Status `finalized` (or `approved_with_edits` in events); released text includes your edit |
| Wellness negative control | Start **CR-005** | `general` + `routine`; no sepsis / ACS flags |
| ACS critical | Start **CR-008** | `cardio` + `critical`; HITL required |

### Automated checks (not the live demo)

```bash
cd backend && python -m pytest
cd frontend && npm test
```

Default suite is mock-only. Do not add live-LLM tests to CI.

### If something looks broken

- **backend unreachable** — uvicorn is not on `8000`, or you opened the UI before the API started.
- **Run assistant disabled** — paste text, pick a file, or use a library **Start** button. Empty form is intentional.
- **Chat disabled** — run is not `finalized` yet. Approve first.
- **No guidelines** — from repo root run `python scripts/ingest_rag.py` once, then retry CR-001. Mock retrieve still works from the lexical index under `data/guidelines/`.
- **Wrong ports** — API `8000`, Vite `5173`. Vite proxies `/api` to `127.0.0.1:8000`.

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

Contracts: `backend/app/contracts.py`.

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
