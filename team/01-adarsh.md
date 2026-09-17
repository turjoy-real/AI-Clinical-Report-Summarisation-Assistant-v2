# Adarsh — execution order 1 and 5

**Concepts:** HITL (human-in-the-loop) in the product surface  
**Owns:** FastAPI routes, run/case persistence, React UI  
**Does not own:** LangGraph internals (Turjoy), guideline cards (Siva), embeddings/retrieve (Vamsi), patient extract (Radhakrishna), medical extract (Vinayak), SOAP summary (Sneha), recommendations (Lakshmi)

Read [CONTRACTS.md](CONTRACTS.md). Start after Turjoy finishes **T0–T4** (repo exists, `/api/health` works).

---

## Your sequence

| Your order | Global phase | Depends on |
| ---: | --- | --- |
| A1–A4 | Phase 1 — parallel with Siva, Radhakrishna, Vinayak | Turjoy T0 |
| A5–A8 | Phase 5 — after graph pauses for review | Turjoy T6 (`awaiting_review`) |

---

## AI task (yours)

Build the **clinician HITL loop in the UI + API**, not a cosmetic modal:

- Stream agent events while the graph runs
- When status is `awaiting_review`, enable **Approve / Save edits / Reject**
- Persist the decision in the run database so a browser refresh does not lose the draft
- Disable "Run assistant" until there is text, a file, or a library case
- Keep a persistent **Not for clinical use** banner on every page

You may use an LLM later for UI copy or to draft error messages, but the HITL state machine must be real.

---

## Prompt A1 — FastAPI routes + run store

```
Implement the HTTP API for an educational clinical assistant (NOT for clinical use).

Files: backend/app/api/routes.py, backend/app/memory/store.py, backend/app/main.py

Persistence: JSON files under backend/.runs/records/ plus an in-memory index. SQLite is OK if you prefer. Do not require Postgres.

Models: use backend/app/contracts.py and add RunRecord with
run_id, case_id, status, summary, recommendations, lab_flags, retrieved_docs,
safety_flags, citations, analysis, events, chat_history, human_decision, created_at, updated_at.

Routes:
GET  /api/health
GET  /api/cases            # read data/cases.json
GET  /api/cases/{id}       # include report text
POST /api/runs             # form: case_id and/or text and/or file
GET  /api/runs
GET  /api/runs/{id}
GET  /api/runs/{id}/events # SSE, poll the record's events list
POST /api/runs/{id}/review # body ReviewRequest (approve|edit|reject)
POST /api/runs/{id}/chat
GET  /api/metrics          # stub zeros until Turjoy fills it
POST /api/rag/reindex      # call Siva ingest_guideline_corpus then Vamsi embed_guidelines; 501 if missing

For POST /api/runs, if Turjoy's start_run exists, call it. If not, create a run with status=running and a fake router event so the UI can be developed.

CORS for localhost:5173.
```

**Done when:** `GET /api/cases` lists CR-001.

---

## Prompt A2 — React app shell

```
Build frontend with Vite, React, TypeScript, Tailwind.

Pages:
- / library of synthetic cases
- /workspace/:runId (or query) workspace
- /observability (empty page that will fetch /api/metrics)

Layout: sticky disclaimer banner "Educational prototype. Not for clinical use."
Components: Layout, Disclaimer, Timeline, HitlDrawer, ChatPanel, LabTable

frontend/src/api.ts wrappers for every backend route.
frontend/src/types.ts matching the API JSON.

No authentication. No real patient data. Use a calm clinical UI, not a consumer chatbot look.
```

---

## Prompt A3 — Case library page

```
Library.tsx: fetch GET /api/cases. Cards show case_id, title, specialty, urgency.
Clicking a case shows the report preview and a button "Run assistant" that POST /api/runs with case_id, then navigates to the workspace.

Empty and error states required.
Urgency critical should be visually distinct but not alarming animation spam.
```

---

## Prompt A4 — Workspace: upload, paste, run

```
Workspace allows three inputs: pick library case, paste text, upload .md/.txt/.pdf.
"Run assistant" disabled when all inputs empty.

After POST /api/runs, subscribe to GET /api/runs/{id}/events (SSE) and render Timeline of agent names + decisions.
Poll GET /api/runs/{id} until status is awaiting_review, ingest_failed, or finalized.

ingest_failed: show recovery copy asking the clinician to paste text. Do not show HITL buttons.
```

**Pause here until Turjoy's graph actually interrupts.** You can keep using fake events.

---

## Prompt A5 — HITL drawer (core AI-product task)

```
HitlDrawer.tsx appears only when status === awaiting_review.

Show the draft summary, recommendations, citations, safety_flags, lab flags.
Actions:
- Approve → POST review {decision:approve}
- Save edits → textarea with edited recommendation text → {decision:edit, edits}
- Reject → textarea feedback → {decision:reject, feedback}

Buttons disabled while the request is in flight.
After approve/edit, UI should move to finalized and enable ChatPanel.
After reject, wait for awaiting_review again (revision cycle).

Add a Vitest/RTL test: Approve / Save edits / Reject render and enable when awaiting_review.
Add a test: disclaimer banner contains "Not for clinical use".
Add a test: Run assistant disabled with empty input.
```

---

## Prompt A6 — Timeline + labs + chat

```
Timeline: render each event's agent and decision (e.g. router, fanout, rag).
LabTable: medical labs from the run record.
ChatPanel: enabled only after finalized. POST /api/runs/{id}/chat.
If chat API is stubbed, show a disabled state with "Available after approval".

SSE should not duplicate events; track last index.
```

---

## Prompt A7 — persistence across refresh

```
If the user reloads /workspace/:runId, load GET /api/runs/{id} and restore summary, HITL, chat history.
Do not create a second run.
If the backend lost the LangGraph checkpoint but the JSON record still has a draft, Approve must still finalize (Turjoy may add a fallback — call it if present).
```

---

## Prompt A8 — polish for demo

```
- Health indicator on the layout (mock vs live from /api/health)
- Loading skeletons, not spinners on every keystroke
- Accessibility: buttons have names, banner is not only color
- README section: how to npm run dev and which ports
Keep Observability page as a simple metrics table; Turjoy owns the numbers.
```

---

## Handoff

Tell Turjoy when `POST /api/runs/{id}/review` is wired. Tell Sneha and Lakshmi the workspace HITL drawer is where their summary and recs appear — they should not build a second UI.
