import type { Metadata } from "next";
import report from "../../../public/report.json";

export const metadata: Metadata = { title: "Data quality · Corpus Sieve" };

const fmt = (n: number) => n.toLocaleString("en-US");

function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <p className="text-sm text-ink-2">{label}</p>
      <p className="mt-1 text-3xl font-semibold">{fmt(value)}</p>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
    </div>
  );
}

function Section({ title, intro, children }: { title: string; intro?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {intro && <p className="max-w-3xl text-sm text-ink-2">{intro}</p>}
      </div>
      {children}
    </section>
  );
}

/** Horizontal bars, one series: characters removed per cleaning step. */
function CleaningChart() {
  const max = Math.max(...report.cleaning.map((s) => s.chars_removed), 1);
  return (
    <table className="w-full text-sm">
      <thead className="sr-only">
        <tr>
          <th>Step</th>
          <th>Characters removed</th>
        </tr>
      </thead>
      <tbody>
        {report.cleaning.map((s) => (
          <tr key={s.step} className="border-b border-line last:border-0">
            <td className="w-1/3 py-2 pr-4 align-top">
              <code className="text-ink">{s.step}</code>
              <p className="text-xs text-muted">{s.description}</p>
            </td>
            <td className="py-2">
              <div className="flex items-center gap-2">
                {s.chars_removed > 0 && (
                  <div
                    className="mark h-3"
                    style={{ width: `${(Math.max(s.chars_removed, 0) / max) * 80}%` }}
                    tabIndex={0}
                  >
                    <div className="fill h-3 w-full rounded-r bg-accent" />
                    <span className="tip">
                      <strong>{fmt(s.chars_removed)}</strong> characters · {s.step}
                    </span>
                  </div>
                )}
                <span className="tabular-nums text-ink-2">{fmt(s.chars_removed)}</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Columns, one series: chunk-length histogram. */
function ChunkHistogram({ bins }: { bins: { from: number; to: number; count: number }[] }) {
  const peak = Math.max(...bins.map((b) => b.count), 1);
  const top = Math.ceil(peak / 50) * 50;
  const ticks = [top, top / 2, 0];
  const plotHeight = 160;
  return (
    <figure>
      <div className="flex">
        <div
          className="flex w-10 flex-col justify-between pr-2 text-right text-xs tabular-nums text-muted"
          style={{ height: plotHeight }}
        >
          {ticks.map((t) => (
            <span key={t} className="-translate-y-1/2 first:translate-y-0 last:translate-y-0">
              {t}
            </span>
          ))}
        </div>
        <div className="relative flex-1">
          <div className="absolute inset-x-0 top-0 border-t border-line" />
          <div className="absolute inset-x-0 border-t border-line" style={{ top: plotHeight / 2 }} />
          <div
            className="relative flex items-end justify-around gap-[2px] border-b border-baseline"
            style={{ height: plotHeight }}
          >
            {bins.map((b) => (
              <div
                key={b.from}
                className="mark flex h-full flex-1 items-end justify-center"
                tabIndex={0}
                aria-label={`${b.from}–${b.to - 1} characters: ${b.count} chunks`}
              >
                <div
                  className="fill w-full max-w-6 rounded-t bg-accent"
                  style={{ height: `${(b.count / top) * 100}%` }}
                />
                <span className="tip">
                  <strong>{b.count}</strong> chunks · {b.from}–{b.to - 1} characters
                </span>
              </div>
            ))}
          </div>
          <div className="flex justify-around gap-[2px] pt-1 text-xs tabular-nums text-muted">
            {bins.map((b) => (
              <span key={b.from} className="flex-1 text-center">
                {b.from}
              </span>
            ))}
          </div>
        </div>
      </div>
      <figcaption className="mt-1 text-center text-xs text-muted">Chunk length in characters (bin start)</figcaption>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-ink-2">Show as a table</summary>
        <table className="mt-2 text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="pr-6 font-normal">Characters</th>
              <th className="font-normal">Chunks</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {bins.map((b) => (
              <tr key={b.from}>
                <td className="pr-6">
                  {b.from}–{b.to - 1}
                </td>
                <td>{b.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

export default function QualityPage() {
  const { totals, chunks, embeddings } = report;
  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-semibold">Data-quality report</h1>
        <p className="mt-1 max-w-3xl text-ink-2">
          Every raw document is cleaned and checked before it is chunked and embedded. Documents that fail a
          blocking check go to quarantine with the reason; the PII check only flags. This page reads the{" "}
          <a className="underline" href="/report.json">
            report.json
          </a>{" "}
          written by the last pipeline run.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Stat label="Documents" value={totals.documents} note="40 Wikipedia + 12 synthetic" />
        <Stat label="Kept" value={totals.kept} />
        <Stat label="Quarantined" value={totals.quarantined} />
        <Stat label="Flagged" value={totals.flagged} note="kept, needs review" />
        <Stat label="Chunks" value={chunks.count} />
        <Stat label="Vectors in Qdrant" value={embeddings.points} note={`${embeddings.dimension} dimensions`} />
      </div>

      <Section title="Checks" intro="Per-document checks run on each raw document; the duplicate checks compare the documents that passed them.">
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="px-3 py-2 font-normal">Check</th>
                <th className="px-3 py-2 font-normal">Passes when</th>
                <th className="px-3 py-2 text-right font-normal">Failed</th>
                <th className="px-3 py-2 font-normal">On failure</th>
              </tr>
            </thead>
            <tbody>
              {report.checks.map((c) => (
                <tr key={c.name} className="border-b border-line last:border-0">
                  <td className="px-3 py-2">
                    <code>{c.name}</code>
                  </td>
                  <td className="px-3 py-2 text-ink-2">{c.description}</td>
                  <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">
                    {c.failed} / {c.evaluated}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-ink-2">{c.blocking ? "quarantine" : "flag only"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title={`Quarantine (${report.quarantine.length})`} intro="Kept out of the vector store, with the reason.">
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="px-3 py-2 font-normal">Document</th>
                <th className="px-3 py-2 font-normal">Failed check</th>
                <th className="px-3 py-2 font-normal">Detail</th>
              </tr>
            </thead>
            <tbody>
              {report.quarantine.map((q) => (
                <tr key={q.id} className="border-b border-line align-top last:border-0">
                  <td className="px-3 py-2">
                    {q.title || <span className="text-muted">(no title)</span>}
                    <p className="text-xs text-muted">{q.id}</p>
                  </td>
                  <td className="px-3 py-2">
                    {q.failed.map((f) => (
                      <code key={f.name} className="mr-1 rounded bg-bad-bg px-1.5 py-0.5 text-bad">
                        {f.name}
                      </code>
                    ))}
                  </td>
                  <td className="px-3 py-2 text-ink-2">{q.failed.map((f) => f.detail).join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {report.flagged.map((f) => (
          <p key={f.id} className="rounded-md bg-warn-bg px-3 py-2 text-sm text-warn">
            Flagged, not quarantined: <strong>{f.title}</strong> ({f.id}) —{" "}
            {f.flags.map((x) => `${x.name}: ${x.detail}`).join("; ")}
          </p>
        ))}
      </Section>

      <Section title="Characters removed per cleaning step" intro="Summed over all 52 documents, in the order the steps run.">
        <div className="rounded-lg border border-line bg-surface p-4">
          <CleaningChart />
        </div>
      </Section>

      <Section
        title="Chunk lengths"
        intro={`${fmt(chunks.count)} chunks from the kept documents: a Markdown heading split, then ${chunks.chunk_size}-character pieces with ${chunks.chunk_overlap} overlap. Mean ${chunks.mean_chars}, min ${chunks.min_chars}, max ${chunks.max_chars} characters; ${chunks.dropped_empty} empty and ${chunks.dropped_short} too-short chunks dropped.`}
      >
        <div className="rounded-lg border border-line bg-surface p-4 pt-6">
          <ChunkHistogram bins={chunks.histogram} />
        </div>
      </Section>

      <Section title="Embeddings">
        <p className="max-w-3xl text-sm text-ink-2">
          {embeddings.model}, {embeddings.dimension} dimensions, {embeddings.distance} distance; {embeddings.checks}.
          Point IDs are uuid5 of the document hash and chunk index, so re-running the pipeline adds nothing.
        </p>
      </Section>
    </div>
  );
}
