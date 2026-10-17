"""Vercel Python function: run the pipeline's cleaning, per-document checks and
chunking on a pasted document. No embedding, and no corpus (duplicate) checks."""

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.chunk import chunk_document
from pipeline.clean import clean_document
from pipeline.report import STEP_DESCRIPTIONS
from pipeline.validate import document_checks

MAX_TEXT_CHARS = 2000
MAX_TITLE_CHARS = 200


def inspect(title: str, text: str) -> dict:
    raw = {"id": "pasted", "title": title, "source": "pasted", "url": "", "license": "", "text": text}
    clean = clean_document(raw)
    checks = document_checks(raw, clean)
    chunks, dropped = chunk_document(clean)
    return {
        "cleaning": [
            {"step": step, "description": STEP_DESCRIPTIONS[step], "chars_removed": removed}
            for step, removed in clean.removed.items()
        ],
        "cleaned_text": clean.text,
        "checks": [c.model_dump() for c in checks],
        "quarantined": any(not c.passed and c.blocking for c in checks),
        "chunks": [{"section": c.section, "text": c.text} for c in chunks],
        "dropped_chunks": {"empty": dropped["empty"], "short": dropped["short"]},
    }


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("content-length") or 0)
        if length > 50_000:
            return self._send(413, {"error": "Request too large."})
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("title", ""), str) \
                or not isinstance(body.get("text"), str):
            return self._send(400, {"error": 'Send JSON like {"title": "...", "text": "..."}.'})
        title, text = body.get("title", ""), body["text"]
        if len(text) > MAX_TEXT_CHARS or len(title) > MAX_TITLE_CHARS:
            return self._send(413, {"error": f"The text is limited to {MAX_TEXT_CHARS} characters "
                                             f"and the title to {MAX_TITLE_CHARS}."})
        self._send(200, inspect(title, text))

    def _send(self, status: int, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
