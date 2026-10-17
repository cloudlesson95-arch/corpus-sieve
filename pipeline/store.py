"""Qdrant collection, idempotent upserts and search."""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from pipeline.embed import DIMENSION
from pipeline.files import env
from pipeline.models import Chunk

COLLECTION = "corpus-sieve"
INDEXED_FIELDS = ("source", "title", "doc_id")  # doc_id: deletes filter on it


def point_id(doc_hash: str, chunk_index: int) -> str:
    """Deterministic point ID, so re-upserting the same chunk overwrites it."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_hash}:{chunk_index}"))


def get_client() -> QdrantClient:
    return QdrantClient(url=env("QDRANT_URL"), api_key=env("QDRANT_API_KEY"), timeout=60)


def ensure_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION):
        client.create_collection(COLLECTION, vectors_config=VectorParams(size=DIMENSION, distance=Distance.COSINE))
        for field in INDEXED_FIELDS:
            client.create_payload_index(COLLECTION, field_name=field, field_schema=PayloadSchemaType.KEYWORD)


def stored_documents(client: QdrantClient) -> dict[str, tuple[set[str], int]]:
    """doc_id -> (document hashes stored for it, number of points)."""
    docs: dict[str, tuple[set[str], int]] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            COLLECTION, limit=1000, offset=offset, with_payload=["doc_id", "doc_hash"], with_vectors=False,
        )
        for p in points:
            hashes, n = docs.get(p.payload["doc_id"], (set(), 0))
            docs[p.payload["doc_id"]] = (hashes | {p.payload["doc_hash"]}, n + 1)
        if offset is None:
            return docs


def doc_filter(doc_id: str) -> Filter:
    return Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])


def delete_document(client: QdrantClient, doc_id: str) -> int:
    """Delete every point of a document; return how many there were."""
    n = client.count(COLLECTION, count_filter=doc_filter(doc_id), exact=True).count
    client.delete(COLLECTION, points_selector=FilterSelector(filter=doc_filter(doc_id)), wait=True)
    return n


def upsert_chunks(client: QdrantClient, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    client.upsert(COLLECTION, wait=True, points=[
        PointStruct(id=point_id(c.doc_hash, c.chunk_index), vector=v, payload=c.model_dump())
        for c, v in zip(chunks, vectors)
    ])


def search(client: QdrantClient, vector: list[float], limit: int = 5, source: str | None = None) -> list[dict]:
    query_filter = Filter(must=[FieldCondition(key="source", match=MatchValue(value=source))]) if source else None
    points = client.query_points(
        COLLECTION, query=vector, limit=limit, query_filter=query_filter, with_payload=True,
    ).points
    return [{"score": round(p.score, 4), **p.payload} for p in points]


def count() -> int:
    return get_client().count(COLLECTION, exact=True).count
