"""Write data/quarantine.json and the public data-quality report."""

from collections import Counter

from pipeline.clean import STEPS
from pipeline.files import QUARANTINE_PATH, REPORT_PATH, read_json, write_json
from pipeline.models import CleanDoc, DocReport
from pipeline.validate import CHECKS

STEP_DESCRIPTIONS = {
    "fix_encoding": "ftfy repairs mojibake, curly quotes and control characters",
    "normalize_unicode": "Unicode NFC normalisation",
    "strip_html": "HTML tags, scripts, styles, comments and entities",
    "strip_wiki_leftovers": "Edit and citation markers, 'See also'/'References' tails",
    "normalize_headings": "Wiki headings to Markdown ('== H ==' to '## H')",
    "remove_boilerplate": "Cookie, navigation, footer and repeated lines",
    "collapse_whitespace": "Runs of spaces and blank lines",
}


def failures(report: DocReport, blocking: bool) -> list[dict]:
    return [
        {"name": c.name, "detail": c.detail}
        for c in report.checks if not c.passed and c.blocking == blocking
    ]


def build_report(reports: list[DocReport], cleaned: list[CleanDoc]) -> dict:
    quarantined = [r for r in reports if r.quarantined]
    evaluated = Counter(c.name for r in reports for c in r.checks)
    failed = Counter(c.name for r in reports for c in r.checks if not c.passed)
    by_source: dict[str, dict[str, int]] = {}
    for r in reports:
        counts = by_source.setdefault(r.source or "(missing)", {"documents": 0, "kept": 0})
        counts["documents"] += 1
        counts["kept"] += not r.quarantined
    return {
        "totals": {
            "documents": len(reports),
            "kept": len(reports) - len(quarantined),
            "quarantined": len(quarantined),
            "flagged": sum(bool(r.flagged) for r in reports),
        },
        "sources": dict(sorted(by_source.items())),
        "checks": [
            {"name": name, "description": description, "blocking": name != "pii",
             "evaluated": evaluated[name], "failed": failed[name]}
            for name, description in CHECKS.items()
        ],
        "cleaning": [
            {"step": step.__name__, "description": STEP_DESCRIPTIONS[step.__name__],
             "chars_removed": sum(d.removed[step.__name__] for d in cleaned)}
            for step in STEPS
        ],
        "quarantine": [
            {"id": r.id, "title": r.title, "source": r.source, "failed": failures(r, blocking=True)}
            for r in quarantined
        ],
        "flagged": [
            {"id": r.id, "title": r.title, "source": r.source, "flags": failures(r, blocking=False)}
            for r in reports if r.flagged
        ],
        "documents": [
            {"id": d.id, "title": d.title, "source": d.source, "url": d.url, "license": d.license,
             "status": "quarantined" if r.quarantined else "flagged" if r.flagged else "kept"}
            for d, r in zip(cleaned, reports)
        ],
    }


def write_outputs(reports: list[DocReport], cleaned: list[CleanDoc], extra: dict | None = None) -> None:
    """Write quarantine.json and report.json. Sections in `extra` (chunks, embeddings) are added;
    without them, the sections from the previous ingest run are kept."""
    write_json(QUARANTINE_PATH, [
        {"id": r.id, "title": r.title, "failed_checks": r.failed,
         "details": {f["name"]: f["detail"] for f in failures(r, blocking=True)}}
        for r in reports if r.quarantined
    ])
    report = build_report(reports, cleaned)
    previous = read_json(REPORT_PATH) if REPORT_PATH.exists() else {}
    for key in ("chunks", "embeddings"):
        if key in previous:
            report[key] = previous[key]
    report.update(extra or {})
    write_json(REPORT_PATH, report)
