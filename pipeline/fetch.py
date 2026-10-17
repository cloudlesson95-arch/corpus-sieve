"""Download the Wikipedia snapshot into data/raw/ (run once, then commit).

Usage: uv run python -m pipeline.fetch
"""

import re
import time

import httpx

from pipeline.clean import TAIL_SECTIONS
from pipeline.files import RAW_DIR, write_json

API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "corpus-sieve/0.1 (portfolio demo of a document ingestion pipeline; python-httpx)"
LICENSE = "CC BY-SA 4.0"

# Body text kept per article, cut at a section boundary. About 10k characters
# per article keeps the corpus near 600 chunks, which embeds within one day of
# the Gemini free tier.
MAX_BODY_CHARS = 10_000

# source -> article titles. The source is the topic feed a document came in
# through; search can filter on it.
ARTICLES = {
    "solar": [
        "Solar power", "Photovoltaics", "Solar cell", "Concentrated solar power",
        "Solar thermal energy", "Photovoltaic power station", "Agrivoltaics",
    ],
    "wind": [
        "Wind power", "Wind turbine", "Offshore wind power", "Wind farm",
        "Vertical-axis wind turbine", "Floating wind turbine",
    ],
    "hydro-marine": [
        "Hydroelectricity", "Pumped-storage hydroelectricity", "Run-of-the-river hydroelectricity",
        "Tidal power", "Wave power", "Ocean thermal energy conversion", "Marine energy",
    ],
    "geothermal-bio": [
        "Geothermal energy", "Geothermal power", "Ground source heat pump",
        "Bioenergy", "Biomass", "Biogas",
    ],
    "storage": [
        "Energy storage", "Grid energy storage", "Battery energy storage system",
        "Lithium-ion battery", "Flow battery", "Compressed-air energy storage",
        "Flywheel energy storage", "Thermal energy storage", "Hydrogen storage",
    ],
    "grid": [
        "Renewable energy", "Electrical grid", "Smart grid", "Variable renewable energy",
        "Levelized cost of electricity",
    ],
}


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def trim_article(text: str, max_chars: int = MAX_BODY_CHARS) -> str:
    """Keep the lead and whole (sub)sections in order up to max_chars, plus the reference tail.

    The tail stays in the snapshot so the cleaner has real leftovers to remove.
    """
    parts = re.split(r"(?m)^(?===)", text)
    kept, tail = [parts[0]], []
    size, full = len(parts[0]), False
    for part in parts[1:]:
        heading = part.splitlines()[0].strip("= \t").lower()
        if heading in TAIL_SECTIONS:
            tail.append(part)
        elif not full and size + len(part) <= max_chars:
            kept.append(part)
            size += len(part)
        else:
            full = True
    return "".join(kept + tail).strip()


def fetch_article(client: httpx.Client, title: str) -> dict | None:
    params = {
        "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
        "prop": "extracts|info", "inprop": "url",
        "explaintext": "1", "exsectionformat": "wiki", "titles": title,
    }
    for attempt in range(6):
        resp = client.get(API, params=params)
        if resp.status_code != 429:
            break
        wait = int(resp.headers.get("retry-after", 0)) or 10 * 2**attempt
        print(f"rate limited, waiting {wait}s")
        time.sleep(wait)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Wikipedia API error: {data['error']['info']}")
    page = data["query"]["pages"][0]
    if page.get("missing") or not page.get("extract"):
        return None
    return {"title": page["title"], "url": page["fullurl"], "text": page["extract"]}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
        for source, titles in ARTICLES.items():
            for title in titles:
                if (RAW_DIR / f"{slugify(title)}.json").exists():
                    continue  # already in the snapshot; reruns resume
                page = fetch_article(client, title)
                time.sleep(2)
                if page is None:
                    print(f"skip (missing): {title}")
                    continue
                doc_id = slugify(page["title"])
                text = trim_article(page["text"])
                write_json(RAW_DIR / f"{doc_id}.json", {
                    "id": doc_id, "title": page["title"], "source": source,
                    "url": page["url"], "license": LICENSE, "text": text,
                })
                saved += 1
                print(f"{source:15} {doc_id:40} {len(page['text']):>7} -> {len(text):>6} chars")
    print(f"saved {saved} articles to {RAW_DIR}")


if __name__ == "__main__":
    main()
