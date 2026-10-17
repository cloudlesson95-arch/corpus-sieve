"""Pure text-cleaning steps. Each takes text and returns text; clean_text records
how many characters every step removed."""

import hashlib
import html
import re
import unicodedata
from collections import Counter

import ftfy

from pipeline.models import CleanDoc

# Sections Wikipedia appends after the article body.
TAIL_SECTIONS = {
    "see also", "notes", "references", "external links", "further reading",
    "bibliography", "sources", "citations", "footnotes", "notes and references",
    "works cited",
}

BOILERPLATE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    r"\bcookies?\b",
    r"^skip to (main )?content$",
    r"^(menu|search|sign in|log in|sign up|register|back to top|follow us|share)$",
    r"\bprivacy policy\b",
    r"\bterms of (use|service)\b",
    r"\ball rights reserved\b",
    r"^©",
    r"\bnewsletter\b",
    r"^share on\b",
    r"^[^|]{1,30}(\|[^|]{1,30}){2,}$",  # navigation bars: "Home | About | Contact"
]]
MAX_BOILERPLATE_LINE = 120  # longer lines are prose, never boilerplate
MAX_REPEATED_LINE = 80  # short lines that repeat within a document are boilerplate

HTML_DROP_BLOCKS = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>|<!--.*?-->|<!DOCTYPE[^>]*>", re.IGNORECASE | re.DOTALL)
HTML_BLOCK_TAGS = re.compile(
    r"</?(p|div|br|h[1-6]|li|ul|ol|tr|table|section|article|header|footer|nav|body|html|head|title)\b[^>]*>",
    re.IGNORECASE,
)
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
WIKI_MARKERS = re.compile(r"\[\s*edit\s*\]|\[\d+\]|\[citation needed\]", re.IGNORECASE)
# Wikipedia's plain-text export spreads each formula over indented one-symbol
# lines followed by its LaTeX source: "\n  \n    m\n    {\displaystyle m}\n  \n".
WIKI_MATH = re.compile(r"\n(?:[ \t][^\n]*\n)*?[ \t]*\{\\(?:display|text)style ?(.*?)\}[ \t]*\n(?:[ \t]*\n)?")
WIKI_HEADING = re.compile(r"(?m)^(={2,6})\s*(.+?)\s*\1\s*$")
TAIL_HEADING = re.compile(r"(?im)^(?:={2,6}|#{1,6})\s*(" + "|".join(sorted(TAIL_SECTIONS)) + r")\s*=*\s*$")


def fix_encoding(text: str) -> str:
    """Repair mojibake (e.g. 'Ã©' -> 'é'), curly quotes and control characters with ftfy."""
    return ftfy.fix_text(text, unescape_html=False, normalization=None)


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def strip_html(text: str) -> str:
    """Drop script/style/comments, turn block tags into line breaks, remove other tags, decode entities."""
    text = HTML_DROP_BLOCKS.sub("", text)
    text = HTML_BLOCK_TAGS.sub("\n", text)
    text = HTML_TAG.sub("", text)
    return html.unescape(text)


def strip_wiki_leftovers(text: str) -> str:
    """Remove edit and citation markers, keep only the LaTeX of exploded formulas,
    and cut the 'See also'/'References' tail."""
    text = WIKI_MARKERS.sub("", text)
    text = WIKI_MATH.sub(lambda m: " " + m.group(1) + " ", text)
    tail = TAIL_HEADING.search(text)
    return text[: tail.start()] if tail else text


def normalize_headings(text: str) -> str:
    """Turn wiki headings ('== History ==') into Markdown ('## History') for the chunker."""
    return WIKI_HEADING.sub(lambda m: "#" * len(m.group(1)) + " " + m.group(2), text)


def is_heading(line: str) -> bool:
    return line.startswith(("=", "#"))


def boilerplate_flags(lines: list[str]) -> list[bool]:
    """Mark lines that are cookie/navigation/footer text or short lines repeated in the document."""
    stripped = [line.strip() for line in lines]
    counts = Counter(s for s in stripped if s and not is_heading(s) and len(s) <= MAX_REPEATED_LINE)
    flags = []
    for s in stripped:
        pattern = len(s) <= MAX_BOILERPLATE_LINE and any(p.search(s) for p in BOILERPLATE_PATTERNS)
        flags.append(bool(s) and (pattern or counts[s] > 1))
    return flags


def remove_boilerplate(text: str) -> str:
    lines = text.split("\n")
    return "\n".join(line for line, flag in zip(lines, boilerplate_flags(lines)) if not flag)


def collapse_whitespace(text: str) -> str:
    text = re.sub(r"[^\S\n]+", " ", text)  # runs of spaces, tabs, non-breaking spaces
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


STEPS = [
    fix_encoding, normalize_unicode, strip_html, strip_wiki_leftovers,
    normalize_headings, remove_boilerplate, collapse_whitespace,
]


def clean_text(text: str) -> tuple[str, dict[str, int]]:
    """Run every step in order; return the cleaned text and characters removed per step."""
    removed = {}
    for step in STEPS:
        cleaned = step(text)
        removed[step.__name__] = len(text) - len(cleaned)
        text = cleaned
    return text, removed


def doc_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_document(raw: dict) -> CleanDoc:
    """Clean a raw document dict. Missing fields become empty strings; the schema check reports them."""
    raw_text = raw.get("text") if isinstance(raw.get("text"), str) else ""
    text, removed = clean_text(raw_text)
    fields = {k: str(raw.get(k) or "") for k in ("id", "title", "source", "url", "license")}
    return CleanDoc(**fields, text=text, doc_hash=doc_hash(text), removed=removed)
