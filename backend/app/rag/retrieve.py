"""RAG retrieve: embeddings + lexical ranking. Owned by Vamsi.

Embeddings optional (OpenAI first, then Gemini), lexical ranking always available.
Hybrid scoring: blend vector distance with stopword-aware lexical overlap.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from app.contracts import RetrievedDoc, GuidelineChunk
from app.rag.ingest import list_guideline_chunks

# Stopwords: short function words we ignore in lexical scoring
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
    "do", "does", "for", "from", "had", "has", "have", "he", "her", "hers",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "just", "no",
    "not", "of", "on", "or", "she", "so", "some", "that", "the", "their",
    "theirs", "them", "then", "these", "they", "this", "those", "to", "too",
    "up", "was", "we", "were", "what", "when", "which", "who", "will", "with",
    "you", "your"
}

# Topic boosts: keyword → topic
_TOPIC_BOOSTS = {
    "diabetes": ["diabetes", "hba1c", "metformin", "glucose", "a1c"],
    "hypertension": ["hypertension", "blood pressure", "amlodipine", "ace inhibitor"],
    "sepsis": ["sepsis", "lactate", "pneumonia", "fever", "bacteremia"],
    "anemia": ["anemia", "hemoglobin", "ferritin", "hgb"],
    "heart_failure": ["hfref", "bnp", "edema", "chf", "ejection fraction"],
    "aki": ["aki", "ckd", "egfr", "creatinine", "acute kidney"],
    "acs": ["acs", "chest", "troponin", "mi", "acute coronary"],
    "hypothyroidism": ["tsh", "hypothyroid", "levothyroxine"],
    "drug_interactions": ["warfarin", "amiodarone", "simvastatin", "drug interaction"],
}

# Specialty boosts: specialty → topic list
_SPECIALTY_BOOSTS = {
    "endocrine": ["diabetes", "hypothyroidism"],
    "cardio": ["hypertension", "heart_failure", "acs"],
    "infectious_disease": ["sepsis"],
    "renal": ["aki"],
    "heme": ["anemia"],
    "general": [],
}

_COLLECTION_NAME = "educational_guidelines"
_DEFAULT_OPENAI_EMBED_MODEL = "text-embedding-3-small"
_DEFAULT_GEMINI_EMBED_MODEL = "models/text-embedding-004"
_CHROMA_DIR = None  # Set on first call


def _get_chroma_dir() -> Path:
    """Return data/chroma directory, creating if needed."""
    global _CHROMA_DIR
    if _CHROMA_DIR is None:
        repo_root = Path(__file__).resolve().parents[3]
        _CHROMA_DIR = repo_root / "data" / "chroma"
        _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return _CHROMA_DIR


def _get_client():
    """Return a Chroma client, or None if not available."""
    if not CHROMA_AVAILABLE:
        return None
    try:
        chroma_dir = _get_chroma_dir()
        settings = Settings(
            is_persistent=True,
            persist_directory=str(chroma_dir),
            allow_reset=True,
        )
        return chromadb.Client(settings)
    except Exception:
        return None


class _GeminiEmbeddingFunction:
    """Chroma-compatible Gemini embedder using google.generativeai."""

    def __init__(self, api_key: str, model_name: str = _DEFAULT_GEMINI_EMBED_MODEL):
        self._api_key = api_key
        self._model_name = (
            model_name if model_name.startswith("models/") else f"models/{model_name}"
        )

    def name(self) -> str:
        return "gemini"

    def _embed_one(self, genai, text: str) -> list[float]:
        result = genai.embed_content(
            model=self._model_name,
            content=text,
            task_type="retrieval_document",
            request_options={"timeout": 20},
        )
        return list(result["embedding"])

    def __call__(self, input):
        import google.generativeai as genai

        texts = list(input)
        if not texts:
            return []
        genai.configure(api_key=self._api_key)
        try:
            result = genai.embed_content(
                model=self._model_name,
                content=texts,
                task_type="retrieval_document",
                request_options={"timeout": 20},
            )
            embedding = result["embedding"]
            if embedding and isinstance(embedding[0], (int, float)):
                return [list(embedding)]
            return [list(item) for item in embedding]
        except Exception:
            return [self._embed_one(genai, text) for text in texts]


def _openai_embedding_function():
    try:
        from chromadb.utils import embedding_functions

        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return None
        model = os.environ.get("OPENAI_EMBEDDING_MODEL") or _DEFAULT_OPENAI_EMBED_MODEL
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=key,
            model_name=model,
        )
    except Exception:
        return None


def _gemini_embedding_function():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_EMBEDDING_MODEL") or _DEFAULT_GEMINI_EMBED_MODEL
    return _GeminiEmbeddingFunction(api_key=key, model_name=model)


def _get_embedding_function():
    """Return OpenAI embeddings, else Gemini, else None if no key is set."""
    return _openai_embedding_function() or _gemini_embedding_function()


def _upsert_collection(client, embed_fn, ids, texts, metadatas):
    """Create or replace the guideline collection, recovering from dimension mismatch."""
    try:
        collection = client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=embed_fn,
        )
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        return collection
    except Exception:
        try:
            client.delete_collection(_COLLECTION_NAME)
        except Exception:
            pass
        collection = client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=embed_fn,
        )
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        return collection


def embed_guidelines() -> int:
    """Embed all guideline chunks into Chroma. Returns count upserted.

    Uses OpenAI if OPENAI_API_KEY is set, otherwise Gemini if GEMINI_API_KEY is set.
    Returns 0 without error when no key is set or Chroma is unavailable.
    """
    if not CHROMA_AVAILABLE:
        return 0

    embed_fn = _get_embedding_function()
    if not embed_fn:
        return 0

    client = _get_client()
    if not client:
        return 0

    try:
        chunks = list_guideline_chunks()
        if not chunks:
            return 0

        ids = [c.id for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [
            {
                "title": c.title,
                "topic": c.topic,
                "source": c.source,
                "citation": c.citation,
            }
            for c in chunks
        ]
        _upsert_collection(client, embed_fn, ids, texts, metadatas)
        return len(chunks)
    except Exception:
        return 0


def _lexical_score(query: str, chunk: GuidelineChunk) -> float:
    """Compute lexical score: token overlap with stopword removal."""
    q_tokens = {
        t.lower() for t in re.findall(r"\w+", query)
        if t.lower() not in _STOPWORDS and len(t) > 1
    }

    if not q_tokens:
        return 0.0

    hay = f"{chunk.topic} {chunk.title} {chunk.text}".lower()
    hay_tokens = {
        t for t in re.findall(r"\w+", hay)
        if t not in _STOPWORDS and len(t) > 1
    }

    # Jaccard similarity
    if not hay_tokens:
        return 0.0

    overlap = len(q_tokens & hay_tokens)
    union = len(q_tokens | hay_tokens)
    return overlap / union if union > 0 else 0.0


def _apply_topic_boosts(query: str, chunk: GuidelineChunk) -> float:
    """Compute topic boost factor based on keyword matches."""
    q_lower = query.lower()
    boost = 1.0

    for topic, keywords in _TOPIC_BOOSTS.items():
        if chunk.topic == topic:
            for kw in keywords:
                if kw in q_lower:
                    boost += 0.5  # Each matching keyword adds 0.5x

    return min(boost, 3.0)  # Cap at 3x


def _apply_specialty_boost(chunk: GuidelineChunk, specialty: str | None) -> float:
    """Compute specialty boost factor."""
    if not specialty or specialty not in _SPECIALTY_BOOSTS:
        return 1.0

    topics = _SPECIALTY_BOOSTS[specialty]
    if chunk.topic in topics:
        return 1.2  # 20% boost
    return 1.0


def _vector_scores(query: str, collection) -> dict[str, float]:
    """One Chroma query for the note, mapped to chunk-id similarity scores."""
    try:
        n_results = max(1, len(list_guideline_chunks()))
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["distances"],
        )
        scores: dict[str, float] = {}
        if not results or not results.get("ids"):
            return scores
        ids = results["ids"][0]
        distances = (results.get("distances") or [[]])[0]
        for i, rid in enumerate(ids):
            distance = distances[i] if i < len(distances) else 1.0
            scores[rid] = max(0.0, 1.0 - distance)
        return scores
    except Exception:
        return {}


def _vector_score(query: str, chunk: GuidelineChunk, collection) -> float | None:
    """Query Chroma for vector distance, return normalized score or None."""
    return _vector_scores(query, collection).get(chunk.id)


def retrieve_guidelines(
    query: str,
    specialty: str | None = None,
    k: int = 4
) -> list[RetrievedDoc]:
    """Retrieve top-k guideline chunks matching the query.

    Blends lexical (always available) and vector scores (if Chroma is populated).
    Applies topic and specialty boosts to ranking.

    Args:
        query: Search query (empty returns empty list, no crash)
        specialty: Optional medical specialty for boost (endocrine, cardio, etc.)
        k: Number of results (default 4)

    Returns:
        Sorted list of RetrievedDoc by combined score, or empty list if query is empty.
    """
    if not (query or "").strip():
        return []

    chunks = list_guideline_chunks()
    if not chunks:
        return []

    # Try to open Chroma collection for vector scores (same embedder used at index time)
    collection = None
    if CHROMA_AVAILABLE:
        try:
            client = _get_client()
            embed_fn = _get_embedding_function()
            if client and embed_fn:
                try:
                    collection = client.get_collection(
                        name=_COLLECTION_NAME,
                        embedding_function=embed_fn,
                    )
                except Exception:
                    # Collection doesn't exist yet
                    pass
        except Exception:
            pass

    vec_by_id = _vector_scores(query, collection) if collection else {}

    docs: list[RetrievedDoc] = []
    for chunk in chunks:
        # Lexical score (always)
        lex_score = _lexical_score(query, chunk)

        # Vector score (if available) — one query above, not one per chunk
        vec_score = vec_by_id.get(chunk.id)

        # Combine: prefer vector if available, fall back to lexical
        if vec_score is not None:
            base_score = 0.7 * vec_score + 0.3 * lex_score
        else:
            base_score = lex_score

        # Apply boosts
        topic_boost = _apply_topic_boosts(query, chunk)
        spec_boost = _apply_specialty_boost(chunk, specialty)
        final_score = base_score * topic_boost * spec_boost

        docs.append(
            RetrievedDoc(
                id=chunk.id,
                title=chunk.title,
                topic=chunk.topic,
                source=chunk.source,
                text=chunk.text,
                score=final_score,
                citation=chunk.citation,
            )
        )

    # Sort by score, return top-k
    docs.sort(key=lambda d: d.score, reverse=True)
    return docs[:k]
