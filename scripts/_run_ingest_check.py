from backend.app.rag.ingest import ingest_guideline_corpus, list_guideline_chunks


def main():
    n = ingest_guideline_corpus("data/guidelines")
    print("INGESTED", n)
    chunks = list_guideline_chunks()
    print("LOADED", len(chunks))
    for c in chunks:
        if c.topic == "diabetes":
            print("DIABETES CHUNK:", c.id, c.text[:120])
            break


if __name__ == "__main__":
    main()
