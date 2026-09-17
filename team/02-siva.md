# Siva — execution order 1

**Concept:** RAG (corpus + chunking)  
**Owns:** original educational guideline cards, lexical ingest, `list_guideline_chunks()`  
**Does not own:** embeddings, Chroma, or `retrieve_guidelines()` — that is **Vamsi**

Read [CONTRACTS.md](CONTRACTS.md). Start after Turjoy finishes **T0**.

---

## Your sequence

| Your order | Global phase | What |
| ---: | --- | --- |
| SI1 | Phase 1 | Dummy medical-reference documents |
| SI2 | Phase 1 | Chunker |
| SI3 | Phase 1 | Lexical index on disk |
| SI4 | Phase 1 | `ingest_guideline_corpus` + `list_guideline_chunks` |
| SI5 | Phase 1 | Tests + guidelines README |

Vamsi cannot embed until SI4 returns real chunks. Message him when that lands.

---

## AI task (yours)

Use an LLM **as a drafting aid** to write **original** educational cards (you edit every line). Then build the ingest pipeline that turns those cards into chunks.

- Public teaching themes only (MedlinePlus / CDC / WHO / NIDDK *by name*). Never paste copyrighted NICE or UpToDate PDFs.
- No real patients inside the cards.
- Your AI output is the **corpus + chunk index**, not a chatbot.

---

## Prompt SI1 — dummy guideline corpus

```
Create original educational guideline cards as markdown under data/guidelines/.
Audience: student demo. NOT for clinical use. Do not copy copyrighted guidelines.

You may use an LLM to draft, then you must rewrite so each card is original teaching text.

Each file starts with a title, topic, audience line, and citation line pointing at public teaching sources by name only.

Required files:
- diabetes.md          (HbA1c teaching ranges, metformin + kidney, follow-up)
- hypertension.md
- sepsis.md
- anemia.md
- heart_failure.md
- aki.md
- acs.md
- hypothyroidism.md
- lab_critical_values.md
- drug_interactions.md (warfarin, amiodarone, simvastatin teaching — not a full label)
- LICENSE.md stating these are original educational cards

Keep each card under ~250 words. Include a "Suggested retrieval queries" section with keywords.
No real patient stories. Do not implement retrieve_guidelines or Chroma. That is Vamsi's job.
```

**Done when:** 10 topic files exist and diabetes.md mentions HbA1c.

---

## Prompt SI2 — chunker

```
Implement backend/app/rag/ingest.py owned by Siva.

chunk_guidelines(folder) -> list[GuidelineChunk] using the model from contracts.py
(id, title, topic, source, text, citation).

Split on paragraphs; skip LICENSE.md; skip heading-only blocks.
id format: "{topic}-{part}" e.g. diabetes-1.
citation copied from the card's Citations line.

Do not call an embedding API. Do not rank queries.
```

---

## Prompt SI3 — lexical index file

```
When ingest runs, write data/guidelines/.lexical_index.json
with the full chunk list so Vamsi and offline retrieve can read it.

Rebuild is idempotent. Running ingest twice must not duplicate ids.
```

---

## Prompt SI4 — public functions

```
Export exactly:

def ingest_guideline_corpus(guidelines_dir: str) -> int:
    """Chunk cards, write .lexical_index.json, return chunk count."""

def list_guideline_chunks() -> list[GuidelineChunk]:
    """Load chunks from the lexical index. Empty list if ingest has not run."""

Add scripts/ingest_rag.py that only calls ingest_guideline_corpus (not embed).
Adarsh will call ingest_guideline_corpus from POST /api/rag/reindex before Vamsi's embed.

Write a short data/guidelines/README.md: how to add a card, how to ingest, reminder not-for-clinical-use.
```

---

## Prompt SI5 — tests

```
backend/tests/test_rag_ingest.py (no network):

- ingest_guideline_corpus returns > 0
- list_guideline_chunks has a chunk whose topic is diabetes and text mentions HbA1c
- LICENSE.md is not a chunk
- second ingest does not duplicate ids

Do not test retrieve ranking. Vamsi owns that.
```

---

## Handoff

Message **Vamsi**: `list_guideline_chunks()` returns diabetes chunks; lexical index is at `data/guidelines/.lexical_index.json`.  
Do not start retrieve yourself.
