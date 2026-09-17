# Vamsi — execution order 2

**Concept:** RAG (embeddings + retrieve)  
**Owns:** Chroma embeddings, ranking, `retrieve_guidelines()`  
**Does not own:** writing guideline markdown — that is **Siva**

Read [CONTRACTS.md](CONTRACTS.md). Start after Turjoy **T0**. You may code retrieve against a tiny fixture, but ranking tests need Siva's cards (or copy three sample chunks into a test fixture if he is late).

---

## Your sequence

| Your order | Global phase | What |
| ---: | --- | --- |
| VA1 | Phase 2 | Read Siva chunks; embed function |
| VA2 | Phase 2 | Vector DB (Chroma) |
| VA3 | Phase 2 | `retrieve_guidelines()` hybrid rank |
| VA4 | Phase 2 | Specialty / topic boosts |
| VA5 | Phase 2 | Tests |

Sneha and Lakshmi call your retrieve output (via Turjoy). Until VA3 exists they use Turjoy's stub.

---

## AI task (yours)

Stand up a **real retrieve path**, not `if "diabetes" in query`.

1. Embed Siva's chunks into Chroma when `OPENAI_API_KEY` is set
2. Always support **lexical** ranking so `MOCK_LLM=true` / no key still retrieves
3. Export `retrieve_guidelines(query, specialty=None, k=4) -> list[RetrievedDoc]`

Query `"HbA1c 9.2 diabetes"` must return the diabetes card ahead of sepsis.

---

## Prompt VA1 — embed entrypoint

```
Implement backend/app/rag/retrieve.py owned by Vamsi.

def embed_guidelines() -> int:
    Load chunks via list_guideline_chunks() from backend.app.rag.ingest (Siva).
    If that import fails in tests, load data/guidelines/.lexical_index.json yourself.
    If OPENAI_API_KEY is missing, return 0 and do not crash.
    If the key is set, embed each chunk and return the number upserted.

Do not rewrite Siva's markdown files. Do not change chunk ids.
```

---

## Prompt VA2 — Chroma persistence

```
Persist Chroma under data/chroma/ collection name educational_guidelines.
Idempotent upsert by chunk id.
Do not commit huge binary indexes if they are large.
If Chroma is unavailable, lexical retrieve must still work.

Document in a short comment at the top of retrieve.py: embeddings optional, lexical required.
```

---

## Prompt VA3 — retrieve function (the deliverable)

```
def retrieve_guidelines(query: str, specialty: str | None = None, k: int = 4) -> list[RetrievedDoc]:

Behavior:
- Always compute a lexical score (token overlap, stopword removal) over Siva's chunks
- If Chroma is populated, blend vector score with lexical; otherwise lexical only
- Return top-k with id, title, topic, source, text, score, citation
- k default 4 so Sneha/Lakshmi prompts stay small
- Empty query → empty list, no crash
- Do not call an LLM inside retrieve. Retrieval only.
- Do not generate new guideline text.
```

---

## Prompt VA4 — ranking hints

```
Topic hint boosts so educational queries land on the right card:
- diabetes / hba1c / metformin → diabetes
- hypertension / blood pressure / amlodipine → hypertension
- sepsis / lactate / pneumonia / fever → sepsis
- anemia / hemoglobin / ferritin → anemia
- hfref / bnp / edema → heart_failure
- aki / ckd / egfr / creatinine → aki
- chest / troponin / acs → acs
- tsh / hypothyroid → hypothyroidism
- warfarin / amiodarone / simvastatin → drug_interactions

If specialty is provided (endocrine, cardio, infectious_disease, renal, heme, general)
slightly boost matching topics. Do not let specialty wipe lexical evidence.
```

---

## Prompt VA5 — tests

```
backend/tests/test_rag_retrieve.py with no network:

- query "HbA1c 9.2 diabetes" → rank-1 topic diabetes, not sepsis
- query about sepsis / lactate / pneumonia → sepsis card
- retrieve_guidelines never raises on unknown tokens
- embed_guidelines() returns 0 when no OpenAI key (do not skip the test)

If Siva's index is missing in CI, load a minimal fixture of 2 chunks (diabetes vs sepsis) inside the test file only — do not create a second corpus in data/guidelines/.
```

---

## Handoff

Message **Sneha** and **Lakshmi**: `retrieve_guidelines("HbA1c 9.2 diabetes")` returns diabetes.  
Message **Turjoy**: RAG node should import `backend.app.rag.retrieve.retrieve_guidelines`.  
Message **Adarsh**: reindex route is ingest (Siva) then `embed_guidelines()` (you).
