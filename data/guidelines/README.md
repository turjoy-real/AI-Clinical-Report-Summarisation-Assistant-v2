# Guidelines corpus

- How to add a card: create a markdown file in this folder. Start with a title line, then `Topic: <topic>`, `Audience: ...`, and `Citation: <public source names>`. Keep cards ~250 words and avoid real patient stories.
- How to ingest: run `python scripts/ingest_rag.py` or call `ingest_guideline_corpus("data/guidelines")` from the backend. This will write `.lexical_index.json` here.
- Important: content is educational only. Not for clinical use.
