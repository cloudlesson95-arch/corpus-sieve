# Corpus Sieve

A document ingestion pipeline that cleans, validates, chunks and embeds documents into Qdrant, with a public search and data-quality demo.

**Live demo:** https://corpus-sieve.vercel.app

A Python pipeline takes a deliberately messy document set (40 Wikipedia articles on renewable energy and energy storage, plus 12 synthetic problem documents), cleans it, checks its quality, quarantines the bad documents with reasons, then chunks and embeds the rest into a Qdrant vector database. A Next.js demo lets visitors search the result, read the data-quality report, and paste their own document to see how the checks judge it.

## What it shows

| Skill | Where to look |
|---|---|
| Preparing data: load, clean, chunk and embed | [pipeline/clean.py](pipeline/clean.py) has seven pure cleaning steps: ftfy encoding repair, NFC normalisation, HTML stripping, Wikipedia leftovers, Markdown headings, boilerplate lines and whitespace. Each records the characters it removed. [pipeline/chunk.py](pipeline/chunk.py) splits on Markdown headings, then into 800-character pieces with 100 overlap, keeping section titles. [pipeline/embed.py](pipeline/embed.py) embeds in batches with Gemini and retries on rate limits. Tests are in [tests/](tests/) and run in [GitHub Actions](.github/workflows/ci.yml). |
| Checking the quality of input data | [pipeline/validate.py](pipeline/validate.py) runs per-document checks (schema, minimum length, mojibake ratio, boilerplate ratio, markup ratio, language, and PII, which flags without quarantining) and corpus checks (exact duplicates by SHA-256, near duplicates by scikit-learn TF-IDF cosine ≥ 0.9). Failing documents go to [data/quarantine.json](data/quarantine.json) with reasons. [public/report.json](public/report.json) drives the [Data quality page](https://corpus-sieve.vercel.app/quality). |
| Working with a vector database | [pipeline/store.py](pipeline/store.py) manages a Qdrant Cloud collection (cosine, 3072 dimensions) with keyword payload indexes on `source`, `title` and `doc_id`. Point IDs are uuid5 of the document hash and chunk index, so upserts are idempotent. Unchanged documents are skipped, and the points of changed or removed documents are deleted by `doc_id` filter, so a second run adds and deletes nothing. Search supports filtering by `source`. |

## Architecture

```
data/raw/*.json  (40 Wikipedia articles + 12 synthetic problem documents)
   │
   ▼
clean ──► validate ──┬──► quarantine.json + report.json   (11 quarantined, 1 flagged)
   (7 steps)  (7 per-doc + 2 corpus checks)
                     │
                     ▼ 41 kept documents
                   chunk ──► embed ──► Qdrant Cloud "corpus-sieve"
            (headings, then 800/100) (gemini-embedding-2,   (cosine, 3072 dims,
                                     batches of 20)          631 points)

Browser ──► Next.js on Vercel
              ├─ /api/search (TypeScript): presets from public/examples.json,
              │    else rate limit → embed the query (Gemini) → Qdrant query (+ source filter)
              └─ /api/inspect (Python function, api/inspect.py): the same clean →
                   per-document checks → chunk code on pasted text, no embedding
```

`uv run python -m pipeline.ingest` runs the whole offline path: load → clean → validate → chunk → embed → upsert. It writes `data/quarantine.json`, `public/report.json` and `public/examples.json`. The web app only reads those files and queries Qdrant.

## How to run it

You need [uv](https://docs.astral.sh/uv/), Node.js 24, a free [Qdrant Cloud](https://cloud.qdrant.io/) cluster, and a [Gemini API key](https://aistudio.google.com/apikey) from a project without billing (free tier).

1. Copy `.env.example` to `.env.local` and fill in `GOOGLE_API_KEY`, `QDRANT_URL` and `QDRANT_API_KEY`.
2. Python side:

   ```powershell
   uv sync
   uv run pytest -q
   uv run python -m pipeline.validate   # clean + check, writes the reports, no network
   uv run python -m pipeline.ingest     # chunk, embed and upsert into Qdrant
   ```

   The snapshot in `data/raw/` is committed. `uv run python -m pipeline.fetch` and `uv run python -m pipeline.make_messy` rebuild it.
3. Web side:

   ```powershell
   npm install
   npm run dev       # pages and /api/search only
   vercel dev        # also runs the Python function api/inspect.py
   ```

   `vercel dev` runs the Python function with the `python` on your PATH. Put the project's virtualenv first, for example by activating `.venv` before starting it.

On Windows, `curl.exe` re-encodes command-line arguments through the ANSI code page, so a non-ASCII JSON body such as `{"text":"Ã©Ã© short"}` reaches the server already changed. Send such a body from a UTF-8 file instead: `curl --data-binary "@body.json" ...`.

## Data and license

- **Wikipedia articles.** 40 English articles on renewable energy and energy storage, fetched once through the Wikipedia API ([pipeline/fetch.py](pipeline/fetch.py)) and committed. Each is trimmed at a section boundary to about 10,000 characters of body text, with its "See also"/"References" tail kept for the cleaner to remove. That keeps the corpus to 631 chunks, which embed within one day of the Gemini free tier. Every article is grouped under a topic `source` (solar, wind, hydro-marine, geothermal-bio, storage, grid), which the search filter uses. The text is © Wikipedia contributors, licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); the demo footer links every article.
- **Synthetic documents.** [pipeline/make_messy.py](pipeline/make_messy.py) writes 12 deterministic documents, each with one problem: exact duplicate, near duplicate, empty, 20-word stub, mojibake, U+FFFD replacement characters, cookie/navigation boilerplate, German text, missing title, fake emails and phone numbers, HTML page source, and only a reference tail. [data/raw/_expected.json](data/raw/_expected.json) names the check each one must fail, and the tests hold the pipeline to it. Their text was written for this project. The contact details use reserved example domains and 555 numbers.

### Thresholds

| Check | Rule | Measured on |
|---|---|---|
| `min_length` | at least 50 words | cleaned text |
| `mojibake` | (ftfy badness + U+FFFD count) / characters ≤ 0.5% | raw text, since cleaning repairs it |
| `boilerplate` | at most 50% of lines are cookie/navigation/footer or repeated short lines | text with HTML and wiki markup stripped |
| `markup` | HTML tags and entities at most 5% of characters | raw text |
| `language` | langdetect says `en` (seeded; judged only above 200 characters) | cleaned text |
| `near_duplicate` | TF-IDF cosine < **0.9** to every earlier document | cleaned text |

The near-duplicate threshold has a wide margin. The lightly edited copy scores 1.00, and the most similar pair of real articles (Geothermal power and Geothermal energy) scores 0.75.

## Embeddings and the Gemini free tier

- **Model:** `gemini-embedding-2` through the REST endpoint `batchEmbedContents`. Its output is 3072-dimensional and already normalised, so the Qdrant collection uses size 3072 with cosine distance.
- **Task prefixes:** the model takes no `task_type`. Documents are sent as `title: <title - section> | text: <chunk>` and queries as `task: search result | query: <query>`.
- **Free-tier quota:** Google shows the limits only in AI Studio. The 429 responses during ingestion reported `EmbedContentRequestsPerMinutePerUserPerProjectPerModel-FreeTier=100`, and every text in a batch counts as one request. So batching (20 texts per call) saves HTTP calls, not quota.
- **Rate-limit handling:** on 429 or 5xx, [embed.py](pipeline/embed.py) waits the `retryDelay` Google returns, or backs off exponentially. It stops cleanly when a per-day quota is hit. Ingest embeds and upserts document by document, so a stopped run resumes the next day without re-embedding finished documents.
- **Every vector is checked before upsert:** dimension 3072, no NaN or infinite values, non-zero norm.
- **Data use:** free-tier input may be used by Google to improve its products. The corpus is public Wikipedia text, and the search page tells visitors their queries go to Google.

## Demo guard

- **Preset queries.** Five presets are served from `public/examples.json` with no API call:
  - how do pumped hydro plants store energy
  - why are some offshore wind turbines floating
  - how does a flow battery work
  - how is geothermal heat turned into electricity
  - what makes up the levelized cost of electricity
- **Rate limit.** Other queries are limited to 10 per minute per IP. Over the limit, the route returns HTTP 429 with a clear message.
- **Fallback.** If Gemini (including its quota 429) or Qdrant fails, the route returns the cached results of the closest preset with a notice.
- **Inspect cap.** Inspect accepts at most 2,000 characters and never embeds anything.
- **No charges possible.** The Gemini key belongs to a free-tier project without billing.

## Limits

- **The rate limiter is in memory, per serverless instance.** Several warm instances each allow 10 per minute; a shared store such as Redis would make it global.
- **English only.** Other languages are quarantined by design.
- **Small corpus.** 41 trimmed articles and 631 chunks, sized to the free embedding quota.
- **Plain search.** No re-ranking, hybrid keyword search or answer generation; results are the top 5 cosine matches.
- **Manual ingestion.** Ingestion is run by hand (`uv run python -m pipeline.ingest`). There is no scheduler or change feed.
- **Duplicate checks don't run on Inspect.** They need the whole corpus.

## What was learned

- **Measure some checks before cleaning.** Mojibake must be measured on the raw text, because ftfy repairs exactly what the check looks for. Boilerplate is judged on the lines the boilerplate step sees. Length, language and PII are judged on the cleaned text.
- **Real data broke a naive rule.** Wikipedia's plain-text export spreads every formula over indented one-symbol lines, followed by its LaTeX. A "repeated short line" boilerplate rule flagged up to 40% of some real articles as boilerplate. The cleaner now collapses each formula to its LaTeX source.
- **A regex can hang on long text.** `[ \t]+[^\n]*` repeated over many lines backtracked catastrophically on a 10k-character article. Anchoring each line on a single leading whitespace character made it linear.
- **Quota is counted per text.** Gemini's free tier counts every text in a batch as a request, and its 429s carry the quota id and a retry delay worth honouring.
- **Light per-document checks keep the function small.** With scikit-learn imported lazily inside the corpus check, the Vercel Python function installs only `api/requirements.txt` (pydantic, ftfy, langdetect, langchain-text-splitters), not the pipeline's full dependencies.

## Screenshots

- [Search](docs/screenshots/search.png): query box, source filter, preset chips, result cards with score, section and source link.
- [Data quality](docs/screenshots/quality.png): totals, per-check failure counts, quarantine table with reasons, characters removed per cleaning step, chunk-length histogram.
- [Inspect a document](docs/screenshots/inspect.png): a messy example (mojibake) with a pass/fail badge per check, what was cleaned, the cleaned text and its chunks.
