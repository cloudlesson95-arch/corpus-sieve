"use client";

import { useState } from "react";

const MAX_CHARS = 2000;

type Check = { name: string; passed: boolean; detail: string; blocking: boolean };
type InspectResult = {
  cleaning: { step: string; description: string; chars_removed: number }[];
  cleaned_text: string;
  checks: Check[];
  quarantined: boolean;
  chunks: { section: string; text: string }[];
  dropped_chunks: { empty: number; short: number };
};

function Badge({ check }: { check: Check }) {
  const [label, cls] = check.passed
    ? ["pass", "bg-good-bg text-good"]
    : check.blocking
      ? ["fail", "bg-bad-bg text-bad"]
      : ["flag", "bg-warn-bg text-warn"];
  return (
    <span
      className={`inline-block w-16 whitespace-nowrap rounded px-1.5 py-0.5 text-center text-xs font-semibold uppercase ${cls}`}
    >
      {check.passed ? "✓ " : "✕ "}
      {label}
    </span>
  );
}

export function InspectClient({ examples }: { examples: { title: string; text: string }[] }) {
  const [title, setTitle] = useState("Pasted document");
  const [text, setText] = useState("");
  const [next, setNext] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<InspectResult | null>(null);

  async function inspect(t: string, body: string) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/inspect", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: t, text: body }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `Error ${res.status}`);
      setResult(data as InspectResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The request failed.");
    } finally {
      setLoading(false);
    }
  }

  function tryExample() {
    const ex = examples[next % examples.length];
    setNext(next + 1);
    setTitle(ex.title);
    setText(ex.text);
    inspect(ex.title, ex.text);
  }

  const failed = result?.checks.filter((c) => !c.passed && c.blocking).map((c) => c.name) ?? [];
  const flagged = result?.checks.filter((c) => !c.passed && !c.blocking).map((c) => c.name) ?? [];

  return (
    <div className="space-y-6">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          inspect(title, text);
        }}
      >
        <input
          className="w-full rounded-md border border-line bg-surface px-3 py-2 outline-none focus:border-accent"
          value={title}
          maxLength={200}
          onChange={(e) => setTitle(e.target.value)}
          aria-label="Title"
          placeholder="Title"
        />
        <textarea
          className="h-48 w-full rounded-md border border-line bg-surface px-3 py-2 font-mono text-sm outline-none focus:border-accent"
          value={text}
          maxLength={MAX_CHARS}
          onChange={(e) => setText(e.target.value)}
          aria-label="Document text"
          placeholder="Paste a document here, or try a messy example."
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            className="rounded-md bg-accent px-4 py-2 font-medium text-white disabled:opacity-60"
            disabled={loading}
          >
            {loading ? "Inspecting…" : "Inspect"}
          </button>
          <button
            type="button"
            onClick={tryExample}
            disabled={loading}
            className="rounded-md border border-line bg-surface px-4 py-2 text-ink-2 hover:border-accent hover:text-ink"
          >
            Try a messy example
          </button>
          <span className="ml-auto text-xs tabular-nums text-muted">
            {text.length} / {MAX_CHARS}
          </span>
        </div>
      </form>

      {error && <p className="rounded-md bg-bad-bg px-3 py-2 text-sm text-bad">{error}</p>}

      {result && (
        <div className={`space-y-8 ${loading ? "opacity-60" : ""}`} aria-live="polite">
          <p
            className={`rounded-md px-3 py-2 font-medium ${
              failed.length ? "bg-bad-bg text-bad" : flagged.length ? "bg-warn-bg text-warn" : "bg-good-bg text-good"
            }`}
          >
            {failed.length
              ? `Would be quarantined: fails ${failed.join(", ")}.`
              : flagged.length
                ? `Would be kept, but flagged for review: ${flagged.join(", ")}.`
                : "Would be kept: passes every per-document check."}
          </p>

          <section>
            <h2 className="mb-2 text-lg font-semibold">Checks</h2>
            <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
              {result.checks.map((c) => (
                <li key={c.name} className="flex flex-wrap items-baseline gap-3 px-3 py-2 text-sm">
                  <Badge check={c} />
                  <code className="w-28">{c.name}</code>
                  <span className="text-ink-2">{c.detail}</span>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold">What was cleaned</h2>
            <table className="w-full rounded-lg border border-line bg-surface text-sm">
              <tbody>
                {result.cleaning.map((s) => (
                  <tr key={s.step} className="border-b border-line last:border-0">
                    <td className="px-3 py-1.5">
                      <code>{s.step}</code>
                    </td>
                    <td className="px-3 py-1.5 text-ink-2">{s.description}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${s.chars_removed ? "" : "text-muted"}`}>
                      {s.chars_removed} chars
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h3 className="mt-4 mb-1 text-sm font-medium text-ink-2">Cleaned text</h3>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-surface p-3 text-sm">
              {result.cleaned_text || <span className="text-muted">(nothing left)</span>}
            </pre>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold">Chunks ({result.chunks.length})</h2>
            {result.chunks.length === 0 && (
              <p className="text-sm text-muted">
                No chunks of 50+ characters ({result.dropped_chunks.short} too short, {result.dropped_chunks.empty}{" "}
                empty).
              </p>
            )}
            <ol className="space-y-2">
              {result.chunks.map((c, i) => (
                <li key={i} className="rounded-lg border border-line bg-surface p-3 text-sm">
                  <p className="text-xs text-muted">
                    #{i} · {c.section} · {c.text.length} characters
                  </p>
                  <p className="mt-1 whitespace-pre-line text-ink-2">{c.text}</p>
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </div>
  );
}
