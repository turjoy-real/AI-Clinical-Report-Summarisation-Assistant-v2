"""Simple script to build the guideline lexical index (no embedding)."""
from pathlib import Path
from backend.app.rag.ingest import ingest_guideline_corpus


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    guidelines = repo_root / "data" / "guidelines"
    count = ingest_guideline_corpus(str(guidelines))
    print(f"Wrote {count} guideline chunks to {guidelines / '.lexical_index.json'}")


if __name__ == "__main__":
    main()
