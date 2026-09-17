# AI Clinical Report Summarisation Assistant

Educational multi-agent prototype for the UST Enterprise Capstone (Healthcare). A clinician uploads a **synthetic** report. LangGraph agents extract findings, retrieve educational guidelines, draft a summary, then **pause for human approval** before anything is released.

**Not for clinical use.** All patients, labs, and recommendations are synthetic.

Phase 0 (Turjoy T0–T4) is in this repo: contracts, synthetic case library, LLM fallback, LangGraph skeleton, and teammate function stubs.

## Quick start

```bash
cd backend
python3 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health).

**Ports:** backend `8000` (FastAPI/uvicorn), frontend `5173` (Vite dev server, proxies `/api` to `127.0.0.1:8000`). For the UI tests: `cd frontend && npm test` (Vitest + RTL).

## App map (Adarsh — API + UI + run store)

- `backend/app/api/routes.py` — all HTTP routes (health, cases, runs, SSE events, review, chat, metrics, RAG reindex)
- `backend/app/memory/store.py` — run persistence: JSON records under `backend/.runs/records/` + in-memory index
- `frontend/src/api.ts` — typed wrappers for every backend route + duplicate-safe SSE subscription
- Pages: `/` case library · `/workspace/:runId` workspace · `/observability` metrics table
- HITL flow: run reaches `awaiting_review` → `HitlDrawer` enables **Approve / Save edits / Reject** → decision persists in the run record (browser refresh restores it; no second run is created)
- Chat is enabled only after `finalized`; `ingest_failed` asks the clinician to paste text instead
- Persistent banner on every page: **Educational prototype. Not for clinical use.**

## Who builds next

After this bootstrap, Phase 1 can start **in parallel**:

| Person | File | Public function |
| --- | --- | --- |
| **Siva** | `team/02-siva.md` | `ingest_guideline_corpus` / `list_guideline_chunks` |
| **Radhakrishna** | `team/04-radhakrishna.md` | `extract_patient_data` |
| **Vinayak** | `team/05-vinayak.md` | `extract_medical_data` |
| **Adarsh** | `team/01-adarsh.md` | FastAPI + UI shell + run store |

Then **Vamsi** (`team/03-vamsi.md`) after Siva's chunks exist.

See `team/README.md` and `team/CONTRACTS.md`.
