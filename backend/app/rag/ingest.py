"""Chunk and index guideline markdown cards into a lexical JSON index.

Owned by Siva: implements chunking and on-disk lexical index.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..contracts import GuidelineChunk


def _read_lines(path: Path) -> List[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


def _parse_card(path: Path) -> dict:
    lines = [l.strip() for l in _read_lines(path) if l.strip() != ""]
    title = lines[0] if lines else path.stem
    topic = ""
    citation = ""
    # Expect next lines: Topic:, Audience:, Citation:
    for l in lines[1:6]:
        if l.lower().startswith("topic:"):
            topic = l.split(":", 1)[1].strip()
        if l.lower().startswith("citation:") or l.lower().startswith("citations:"):
            citation = l.split(":", 1)[1].strip()
    if not topic:
        topic = path.stem
    return {"title": title, "topic": topic, "citation": citation}


def _split_paragraphs(text: str) -> List[str]:
    paras = []
    cur = []
    for line in text.splitlines():
        if line.strip() == "":
            if cur:
                paras.append("\n".join(cur).strip())
                cur = []
        else:
            cur.append(line)
    if cur:
        paras.append("\n".join(cur).strip())
    # skip heading-only blocks
    return [p for p in paras if not (p.strip().startswith("#") and len(p.strip().splitlines()) == 1)]


def chunk_guidelines(folder: str) -> List[GuidelineChunk]:
    p = Path(folder)
    chunks: List[GuidelineChunk] = []
    files = sorted([x for x in p.glob("*.md") if x.name.lower() != "license.md"])
    for f in files:
        card_meta = _parse_card(f)
        text = f.read_text(encoding="utf-8")
        paras = _split_paragraphs(text)
        part = 1
        for para in paras:
            # skip very short headings
            if len(para.strip()) < 20:
                continue
            chunk_id = f"{card_meta['topic']}-{part}"
            part += 1
            gc = GuidelineChunk(
                id=chunk_id,
                title=card_meta["title"].lstrip("# "),
                topic=card_meta["topic"],
                source=f.name,
                text=para,
                citation=card_meta.get("citation", ""),
            )
            chunks.append(gc)
    return chunks


_LEXICAL_INDEX_NAME = ".lexical_index.json"


def ingest_guideline_corpus(guidelines_dir: str) -> int:
    """Chunk cards, write .lexical_index.json, return chunk count."""
    p = Path(guidelines_dir)
    p.mkdir(parents=True, exist_ok=True)
    chunks = chunk_guidelines(guidelines_dir)
    out = p / _LEXICAL_INDEX_NAME
    # Write idempotently (rebuild every time)
    with out.open("w", encoding="utf-8") as fh:
        json.dump([c.dict() for c in chunks], fh, ensure_ascii=False, indent=2)
    return len(chunks)


def list_guideline_chunks() -> List[GuidelineChunk]:
    """Load chunks from the lexical index. Empty list if ingest has not run."""
    # locate data/guidelines relative to project root
    repo_root = Path(__file__).resolve().parents[3]
    idx = repo_root / "data" / "guidelines" / _LEXICAL_INDEX_NAME
    if not idx.exists():
        return []
    try:
        raw = json.loads(idx.read_text(encoding="utf-8"))
        return [GuidelineChunk(**r) for r in raw]
    except Exception:
        return []
from __future__ import annotations

from pathlib import Path

from app.contracts import GuidelineChunk


def ingest_guideline_corpus(guidelines_dir: str) -> int:
    # Replace stub — owned by Siva
    folder = Path(guidelines_dir)
    if not folder.exists():
        return 0
    return len([path for path in folder.glob("*.md") if path.name.upper() != "LICENSE.md"])


def list_guideline_chunks() -> list[GuidelineChunk]:
    # Replace stub — owned by Siva
    return [
        GuidelineChunk(
            id="diabetes-stub-1",
            title="Educational diabetes teaching card",
            topic="diabetes",
            source="diabetes.md",
            text="HbA1c above target (for example 9.2%) is used in this educational prototype to discuss follow-up, not to order therapy.",
            citation="MedlinePlus diabetes teaching theme",
        )
    ]
