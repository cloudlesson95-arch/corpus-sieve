"""Embeddings with Google's gemini-embedding-2 over the Gemini REST API (free tier).

gemini-embedding-2 takes no task_type; the task goes into the text as a prefix.
"""

import math
import time

import httpx

from pipeline.files import env
from pipeline.models import Chunk

MODEL = "gemini-embedding-2"
DIMENSION = 3072
BATCH_SIZE = 20
MAX_ATTEMPTS = 6
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:batchEmbedContents"


class QuotaExhausted(RuntimeError):
    """The free tier's daily quota is used up; retrying today won't help."""


def document_input(chunk: Chunk) -> str:
    title = chunk.title if chunk.section == "Introduction" else f"{chunk.title} - {chunk.section}"
    return f"title: {title} | text: {chunk.text}"


def query_input(query: str) -> str:
    return f"task: search result | query: {query}"


def check_vector(vector: list[float]) -> None:
    if len(vector) != DIMENSION:
        raise ValueError(f"embedding has dimension {len(vector)}, expected {DIMENSION}")
    if not all(math.isfinite(x) for x in vector):
        raise ValueError("embedding contains NaN or infinite values")
    if math.hypot(*vector) == 0:
        raise ValueError("embedding is a zero vector")


def _quota_info(resp: httpx.Response) -> tuple[list[str], float | None]:
    """Quota ids and the retry delay (seconds) from a Gemini 429 response."""
    try:
        details = resp.json()["error"].get("details", [])
    except (ValueError, KeyError):
        return [], None
    quotas, delay = [], None
    for d in details:
        for v in d.get("violations", []):
            quotas.append(f"{v.get('quotaId')}={v.get('quotaValue')}")
        if "retryDelay" in d:
            delay = float(d["retryDelay"].rstrip("s"))
    return quotas, delay


def _embed_batch(http: httpx.Client, texts: list[str]) -> list[list[float]]:
    body = {"requests": [{"model": f"models/{MODEL}", "content": {"parts": [{"text": t}]}} for t in texts]}
    headers = {"x-goog-api-key": env("GOOGLE_API_KEY")}
    for attempt in range(MAX_ATTEMPTS):
        resp = http.post(API, json=body, headers=headers)
        if resp.status_code == 200:
            return [e["values"] for e in resp.json()["embeddings"]]
        if resp.status_code != 429 and resp.status_code < 500:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")
        quotas, delay = _quota_info(resp)
        if any("PerDay" in q for q in quotas):
            raise QuotaExhausted(f"daily free-tier quota used up ({', '.join(quotas)})")
        wait = delay if delay is not None else min(5 * 2**attempt, 120)
        print(f"  Gemini {resp.status_code} {', '.join(quotas)}; retrying in {wait:.0f}s")
        time.sleep(wait + 1)
    raise RuntimeError(f"embedding failed after {MAX_ATTEMPTS} attempts")


def embed_texts(texts: list[str], http: httpx.Client) -> list[list[float]]:
    """Embed in batches of BATCH_SIZE and check every vector."""
    vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        vectors.extend(_embed_batch(http, texts[start : start + BATCH_SIZE]))
    if len(vectors) != len(texts):
        raise ValueError(f"got {len(vectors)} embeddings for {len(texts)} texts")
    for v in vectors:
        check_vector(v)
    return vectors
