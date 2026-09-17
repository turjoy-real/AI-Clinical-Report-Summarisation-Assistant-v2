# AI Clinical Report Summarisation Assistant

Educational multi-agent prototype for the UST Enterprise Capstone (Healthcare). A clinician uploads a **synthetic** report. LangGraph agents extract findings, retrieve educational guidelines, draft a structured summary, and present a clinician-facing review workflow.

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

## Repository composition

This repository is primarily Python-based, with the following language distribution:

- Python: 93.6%
- TypeScript: 4.0%
- HTML: 1.3%
- Other: 1.1%

The project is centered on the Python backend and agent orchestration layer, while the frontend and supporting UI are kept to a smaller TypeScript footprint.

This project demonstrates how AI can be applied in a healthcare workflow by combining multi-agent reasoning, retrieval-augmented guidance, and human-in-the-loop review to transform a raw clinical report into a structured summary with evidence-backed recommendations while keeping the output transparent and safe for educational use.
