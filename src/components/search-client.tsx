"use client";

import { useState } from "react";
import type { Example, SearchResponse } from "@/lib/types";

export function SearchClient({ presets, sources }: { presets: Example[]; sources: string[] }) {
  const [query, setQuery] = useState(presets[0]?.query ?? "");
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(
    presets[0] ? { query: presets[0].query, results: presets[0].results, cached: true } : null,
  );

  async function search(q: string, src: string) {
    setQuery(q);
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ q, source: src || undefined }),
      });
      const data = (await res.json()) as SearchResponse;
      setResponse(res.ok ? data : { query: q, results: [], cached: false, error: data.error ?? `Error ${res.status}` });
    } catch {
      setResponse({ query: q, results: [], cached: false, error: "The search request failed. Check your connection." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <form
        className="flex flex-col gap-3 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          search(query, source);
        }}
      >
        <input
          className="flex-1 rounded-md border border-line bg-surface px-3 py-2 outline-none focus:border-accent"
          value={query}
          maxLength={200}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about renewable energy or energy storage"
          aria-label="Search query"
        />
        <select
          className="rounded-md border border-line bg-surface px-3 py-2"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          aria-label="Source filter"
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button
          className="rounded-md bg-accent px-4 py-2 font-medium text-white disabled:opacity-60"
          disabled={loading || !query.trim()}
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      <div>
        <p className="text-sm text-muted">Preset queries (served from a cache, no API call):</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {presets.map((p) => (
            <button
              key={p.query}
              type="button"
              onClick={() => {
                setSource("");
                search(p.query, "");
              }}
              className="rounded-full border border-line bg-surface px-3 py-1 text-sm text-ink-2 hover:border-accent hover:text-ink"
            >
              {p.query}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted">
          Other queries are embedded live by Google&apos;s Gemini API (free tier, which may use the input to improve
          Google&apos;s products) and are limited to 10 per minute.
        </p>
      </div>

      {response && (
        <section className={loading ? "opacity-60" : ""} aria-live="polite">
          {response.error && (
            <p className="rounded-md bg-bad-bg px-3 py-2 text-sm text-bad">{response.error}</p>
          )}
          {response.notice && (
            <p className="rounded-md bg-warn-bg px-3 py-2 text-sm text-warn">{response.notice}</p>
          )}
          {!response.error && (
            <p className="mb-3 text-sm text-muted">
              Top {response.results.length} chunks for “{response.query}”
              {response.source ? ` in ${response.source}` : ""}
              {response.cached ? " · cached" : " · live"}
            </p>
          )}
          <ol className="space-y-3">
            {response.results.map((r) => (
              <li key={`${r.doc_id}-${r.chunk_index}`} className="rounded-lg border border-line bg-surface p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="font-medium">
                    {r.title}
                    <span className="font-normal text-ink-2"> · {r.section}</span>
                  </h2>
                  <span className="text-sm tabular-nums text-ink-2">score {r.score.toFixed(3)}</span>
                </div>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-ink-2">{r.text}</p>
                <p className="mt-2 flex flex-wrap gap-x-4 text-xs text-muted">
                  <span>source: {r.source}</span>
                  <span>chunk {r.chunk_index}</span>
                  <a className="text-accent-ink underline" href={r.url} target="_blank" rel="noreferrer">
                    Read the source
                  </a>
                </p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
