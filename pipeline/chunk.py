"""Heading-aware chunking: split on Markdown headings, then into ~800-character pieces."""

import re
from collections import Counter

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from pipeline.models import Chunk, CleanDoc

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MIN_CHUNK_CHARS = 50
HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
HISTOGRAM_BIN = 100

_headings = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS, strip_headers=True)
_pieces = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (section title, chunk text) pairs, before the length checks."""
    out = []
    for part in _headings.split_text(text):
        section = " > ".join(part.metadata[key] for _, key in HEADERS if key in part.metadata)
        for piece in _pieces.split_text(part.page_content):
            out.append((section or "Introduction", re.sub(r"[ \t]+\n", "\n", piece).strip()))
    return out


def chunk_document(doc: CleanDoc) -> tuple[list[Chunk], Counter]:
    """Chunk a cleaned document; drop empty chunks and ones under MIN_CHUNK_CHARS (counted)."""
    chunks, dropped = [], Counter()
    for section, text in split_sections(doc.text):
        if not text:
            dropped["empty"] += 1
        elif len(text) < MIN_CHUNK_CHARS:
            dropped["short"] += 1
        else:
            chunks.append(Chunk(
                doc_id=doc.id, doc_hash=doc.doc_hash, chunk_index=len(chunks), title=doc.title,
                section=section, source=doc.source, url=doc.url, license=doc.license, text=text,
            ))
    return chunks, dropped


def chunk_stats(chunks: list[Chunk], dropped: Counter) -> dict:
    """Length distribution for the report."""
    lengths = [len(c.text) for c in chunks]
    bins = Counter(min(n // HISTOGRAM_BIN, CHUNK_SIZE // HISTOGRAM_BIN - 1) for n in lengths)
    return {
        "count": len(chunks),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "min_chars": min(lengths, default=0),
        "max_chars": max(lengths, default=0),
        "mean_chars": round(sum(lengths) / len(lengths)) if lengths else 0,
        "dropped_empty": dropped["empty"],
        "dropped_short": dropped["short"],
        "histogram": [
            {"from": b * HISTOGRAM_BIN, "to": (b + 1) * HISTOGRAM_BIN, "count": bins[b]}
            for b in range(CHUNK_SIZE // HISTOGRAM_BIN)
        ],
    }
