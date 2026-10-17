"""Data-quality checks.

Per-document checks import only light libraries (pydantic, ftfy, langdetect) so
the Inspect web function can run them; the corpus checks import scikit-learn
lazily inside corpus_checks.

Usage: uv run python -m pipeline.validate
"""

import re

from ftfy.badness import badness
from langdetect import DetectorFactory, LangDetectException, detect
from pydantic import ValidationError

from pipeline.clean import (
    boilerplate_flags,
    clean_document,
    strip_html,
    strip_wiki_leftovers,
)
from pipeline.models import CheckResult, CleanDoc, DocReport, RawDoc

DetectorFactory.seed = 0  # langdetect is random without a seed

MIN_WORDS = 50
MAX_MOJIBAKE_RATIO = 0.005
MAX_BOILERPLATE_RATIO = 0.5
MAX_MARKUP_RATIO = 0.05
LANGDETECT_MIN_CHARS = 200
NEAR_DUPLICATE_THRESHOLD = 0.9

CHECKS = {
    "schema": "Has non-empty id, title and source, and string url, license and text fields",
    "min_length": f"At least {MIN_WORDS} words after cleaning",
    "mojibake": f"Mojibake sequences and U+FFFD replacement characters in the raw text stay under {MAX_MOJIBAKE_RATIO:.1%}",
    "boilerplate": f"Cookie, navigation, footer and repeated lines are at most {MAX_BOILERPLATE_RATIO:.0%} of the lines",
    "markup": f"HTML tags and entities are at most {MAX_MARKUP_RATIO:.0%} of the raw characters",
    "language": f"English according to langdetect (judged when the cleaned text has {LANGDETECT_MIN_CHARS}+ characters)",
    "pii": "No email addresses or phone numbers (flagged for review, not quarantined)",
    "exact_duplicate": "No earlier document has the same cleaned text (SHA-256)",
    "near_duplicate": f"TF-IDF cosine similarity to every earlier document stays below {NEAR_DUPLICATE_THRESHOLD}",
}

MARKUP = re.compile(r"</?[A-Za-z][^>]*>|<!--.*?-->|<!DOCTYPE[^>]*>|&#?\w+;", re.DOTALL)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]?\d{4}(?!\w)")


def check_schema(raw: dict) -> CheckResult:
    try:
        RawDoc.model_validate(raw)
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        return CheckResult(name="schema", passed=False, detail=problems)
    return CheckResult(name="schema", passed=True, detail="all fields present")


def check_min_length(clean_text: str) -> CheckResult:
    words = len(clean_text.split())
    return CheckResult(
        name="min_length", passed=words >= MIN_WORDS,
        detail=f"{words} words after cleaning (minimum {MIN_WORDS})",
    )


def check_mojibake(raw_text: str) -> CheckResult:
    bad = badness(raw_text) + raw_text.count("�")
    ratio = bad / max(len(raw_text), 1)
    return CheckResult(
        name="mojibake", passed=ratio <= MAX_MOJIBAKE_RATIO,
        detail=f"{bad} suspicious sequences in {len(raw_text)} characters ({ratio:.2%})",
    )


def check_boilerplate(raw_text: str) -> CheckResult:
    # Judge the lines the boilerplate step sees: HTML and wiki markup already stripped.
    text = strip_wiki_leftovers(strip_html(raw_text))
    lines = [line for line in text.split("\n") if line.strip()]
    flagged = sum(boilerplate_flags(lines))
    ratio = flagged / max(len(lines), 1)
    return CheckResult(
        name="boilerplate", passed=ratio <= MAX_BOILERPLATE_RATIO,
        detail=f"{flagged} of {len(lines)} lines are boilerplate ({ratio:.0%})",
    )


def check_markup(raw_text: str) -> CheckResult:
    markup = sum(len(m) for m in MARKUP.findall(raw_text))
    ratio = markup / max(len(raw_text), 1)
    return CheckResult(
        name="markup", passed=ratio <= MAX_MARKUP_RATIO,
        detail=f"{markup} of {len(raw_text)} characters are HTML tags or entities ({ratio:.0%})",
    )


def check_language(clean_text: str) -> CheckResult:
    if len(clean_text) < LANGDETECT_MIN_CHARS:
        return CheckResult(name="language", passed=True, detail="too short to judge")
    try:
        lang = detect(clean_text)
    except LangDetectException:
        return CheckResult(name="language", passed=True, detail="no language features found")
    return CheckResult(name="language", passed=lang == "en", detail=f"detected '{lang}'")


def check_pii(clean_text: str) -> CheckResult:
    emails, phones = len(EMAIL.findall(clean_text)), len(PHONE.findall(clean_text))
    detail = f"{emails} email address(es), {phones} phone number(s)"
    return CheckResult(name="pii", passed=not (emails or phones), detail=detail, blocking=False)


def document_checks(raw: dict, clean: CleanDoc) -> list[CheckResult]:
    """Checks that need only the document itself."""
    raw_text = raw.get("text") if isinstance(raw.get("text"), str) else ""
    return [
        check_schema(raw),
        check_min_length(clean.text),
        check_mojibake(raw_text),
        check_boilerplate(raw_text),
        check_markup(raw_text),
        check_language(clean.text),
        check_pii(clean.text),
    ]


def corpus_checks(docs: list[CleanDoc]) -> dict[str, list[CheckResult]]:
    """Exact and near duplicates. In each duplicate group the document with the smallest id is kept."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel

    docs = sorted(docs, key=lambda d: d.id)
    results: dict[str, list[CheckResult]] = {d.id: [] for d in docs}

    first_with_hash: dict[str, str] = {}
    unique = []
    for d in docs:
        original = first_with_hash.setdefault(d.doc_hash, d.id)
        is_copy = original != d.id
        detail = f"same cleaned text as {original}" if is_copy else "no identical text"
        results[d.id].append(CheckResult(name="exact_duplicate", passed=not is_copy, detail=detail))
        if not is_copy:
            unique.append(d)

    if len(unique) > 1:
        tfidf = TfidfVectorizer(stop_words="english").fit_transform([d.text for d in unique])
        sims = linear_kernel(tfidf)  # rows are L2-normalised, so this is cosine similarity
    kept: list[int] = []
    for j, d in enumerate(unique):
        best_i = max(kept, key=lambda i: sims[i, j], default=None)
        best = float(sims[best_i, j]) if best_i is not None else 0.0
        is_near = best >= NEAR_DUPLICATE_THRESHOLD
        detail = f"highest cosine {best:.2f}" + (f" with {unique[best_i].id}" if best_i is not None else "")
        results[d.id].append(CheckResult(name="near_duplicate", passed=not is_near, detail=detail))
        if not is_near:
            kept.append(j)
    return results


def validate_corpus(raw_docs: list[dict]) -> tuple[list[CleanDoc], list[DocReport]]:
    """Clean every document, run the per-document checks, then the corpus checks on the survivors."""
    cleaned = [clean_document(raw) for raw in raw_docs]
    reports = {
        c.id: DocReport(id=c.id, title=c.title, source=c.source, checks=document_checks(raw, c))
        for raw, c in zip(raw_docs, cleaned)
    }
    survivors = [c for c in cleaned if not reports[c.id].quarantined]
    for doc_id, results in corpus_checks(survivors).items():
        reports[doc_id].checks.extend(results)
    return cleaned, list(reports.values())


def main() -> None:
    from pipeline.files import load_raw_docs
    from pipeline.report import write_outputs

    cleaned, reports = validate_corpus(load_raw_docs())
    write_outputs(reports, cleaned)
    quarantined = [r for r in reports if r.quarantined]
    flagged = [r for r in reports if r.flagged]
    print(f"documents: {len(reports)} | kept: {len(reports) - len(quarantined)} | "
          f"quarantined: {len(quarantined)} | flagged: {len(flagged)}")
    for r in quarantined:
        print(f"  quarantined {r.id}: {', '.join(r.failed)}")
    for r in flagged:
        print(f"  flagged     {r.id}: {', '.join(r.flagged)}")


if __name__ == "__main__":
    main()
