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
