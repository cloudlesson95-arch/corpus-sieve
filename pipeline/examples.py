"""Cache search results for the preset queries in public/examples.json.

The demo serves these without calling Gemini, so they keep working when the
free-tier quota or the rate limit is hit. pipeline.ingest refreshes them when
the collection changes.

Usage: uv run python -m pipeline.examples
"""

import httpx
from qdrant_client import QdrantClient

from pipeline.embed import embed_texts, query_input
from pipeline.files import EXAMPLES_PATH, write_json
from pipeline.store import get_client, search

PRESET_QUERIES = [
    "how do pumped hydro plants store energy",
    "why are some offshore wind turbines floating",
    "how does a flow battery work",
    "how is geothermal heat turned into electricity",
    "what makes up the levelized cost of electricity",
]
RESULT_FIELDS = ("score", "title", "section", "url", "source", "text", "doc_id", "chunk_index")


def write_examples(client: QdrantClient, http: httpx.Client) -> None:
    vectors = embed_texts([query_input(q) for q in PRESET_QUERIES], http)
    write_json(EXAMPLES_PATH, [
        {"query": q, "results": [{k: hit[k] for k in RESULT_FIELDS} for hit in search(client, v, limit=5)]}
        for q, v in zip(PRESET_QUERIES, vectors)
    ])
    print(f"  cached results for {len(PRESET_QUERIES)} preset queries in {EXAMPLES_PATH.name}")


if __name__ == "__main__":
    with httpx.Client(timeout=60) as http:
        write_examples(get_client(), http)
