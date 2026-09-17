from __future__ import annotations

from app.contracts import RetrievedDoc
from app.rag.ingest import list_guideline_chunks


def embed_guidelines() -> int:
    # Replace stub — owned by Vamsi
    return 0


def retrieve_guidelines(query: str, specialty: str | None = None, k: int = 4) -> list[RetrievedDoc]:
    # Replace stub — owned by Vamsi
    if not (query or "").strip():
        return []
    q = query.lower()
    docs: list[RetrievedDoc] = []
    for chunk in list_guideline_chunks():
        hay = f"{chunk.topic} {chunk.title} {chunk.text}".lower()
        score = 1.0 if any(token in hay for token in q.split() if len(token) > 3) else 0.2
        if "diabetes" in q or "hba1c" in q or "9.2" in q:
            if chunk.topic == "diabetes":
                score += 5
        if specialty == "endocrine" and chunk.topic == "diabetes":
            score += 1
        docs.append(
            RetrievedDoc(
                id=chunk.id,
                title=chunk.title,
                topic=chunk.topic,
                source=chunk.source,
                text=chunk.text,
                score=score,
                citation=chunk.citation,
            )
        )
    docs.sort(key=lambda item: item.score, reverse=True)
    return docs[:k]
