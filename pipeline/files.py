"""Paths and JSON helpers shared by the pipeline scripts."""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
EXPECTED_PATH = RAW_DIR / "_expected.json"
QUARANTINE_PATH = ROOT / "data" / "quarantine.json"
REPORT_PATH = ROOT / "public" / "report.json"
EXAMPLES_PATH = ROOT / "public" / "examples.json"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_raw_docs() -> list[dict]:
    """Load every raw document as a plain dict, sorted by file name.

    Documents are kept as dicts because some are deliberately broken
    (missing fields); the schema check decides what is valid.
    """
    return [read_json(p) for p in sorted(RAW_DIR.glob("*.json")) if not p.name.startswith("_")]
