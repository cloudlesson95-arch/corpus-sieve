"""Run the whole pipeline: load -> clean -> validate -> chunk -> embed -> upsert.

Idempotent: documents whose hash and chunk count are unchanged in Qdrant are
skipped, changed ones are replaced, and removed or quarantined ones are deleted.
Embedding and upsert go document by document, so a run stopped by the Gemini
free-tier quota resumes where it left off.

Usage: uv run python -m pipeline.ingest
"""

import sys
from collections import Counter

import httpx

from pipeline import examples
from pipeline.chunk import chunk_document, chunk_stats
from pipeline.embed import DIMENSION, MODEL, QuotaExhausted, document_input, embed_texts
from pipeline.files import load_raw_docs
from pipeline.report import write_outputs
from pipeline.store import (
    COLLECTION,
    delete_document,
    ensure_collection,
    get_client,
    stored_documents,
    upsert_chunks,
)
from pipeline.validate import validate_corpus


def main() -> None:
    cleaned, reports = validate_corpus(load_raw_docs())
    kept_ids = {r.id for r in reports if not r.quarantined}
    kept = [d for d in cleaned if d.id in kept_ids]

    chunks_by_doc, dropped = {}, Counter()
    for doc in kept:
        chunks_by_doc[doc.id], doc_dropped = chunk_document(doc)
        dropped.update(doc_dropped)
    all_chunks = [c for chunks in chunks_by_doc.values() for c in chunks]

    client = get_client()
    ensure_collection(client)
    stored = stored_documents(client)

    deleted = sum(delete_document(client, doc_id) for doc_id in stored.keys() - kept_ids)
    new = unchanged = 0
    stopped = None
    with httpx.Client(timeout=60) as http:
        for doc in kept:
            chunks = chunks_by_doc[doc.id]
            if stored.get(doc.id) == ({doc.doc_hash}, len(chunks)):
                unchanged += len(chunks)
                continue
            try:
                vectors = embed_texts([document_input(c) for c in chunks], http)
            except QuotaExhausted as e:
                stopped = e
                break
            if doc.id in stored:
                deleted += delete_document(client, doc.id)
            upsert_chunks(client, chunks, vectors)
            new += len(chunks)
            print(f"  upserted {doc.id}: {len(chunks)} chunks")

        if not stopped and (new or deleted or not examples.EXAMPLES_PATH.exists()):
            try:
                examples.write_examples(client, http)
            except QuotaExhausted as e:
                stopped = e

    points = client.count(COLLECTION, exact=True).count
    write_outputs(reports, cleaned, extra={
        "chunks": chunk_stats(all_chunks, dropped),
        "embeddings": {
            "model": MODEL, "dimension": DIMENSION, "distance": "cosine", "points": points,
            "checks": "every vector is checked for dimension, NaN/infinite values and zero norm before upsert",
        },
    })
    quarantined = len(reports) - len(kept)
    print(
        f"documents: {len(reports)} | kept: {len(kept)} | quarantined: {quarantined} | "
        f"chunks: {len(all_chunks)} | new chunks upserted: {new} | unchanged: {unchanged} | "
        f"deleted: {deleted} | points in collection: {points}"
    )
    if stopped:
        sys.exit(f"stopped early: {stopped}. Run again after the quota resets (midnight Pacific time); "
                 "finished documents are skipped.")


if __name__ == "__main__":
    main()
