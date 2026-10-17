import { QdrantClient } from "@qdrant/js-client-rest";
import examples from "../../../../public/examples.json";
import report from "../../../../public/report.json";
import type { Example, SearchResult } from "../../../lib/types";

// Must match pipeline/embed.py and pipeline/store.py.
const MODEL = "gemini-embedding-2";
const COLLECTION = "corpus-sieve";

const RATE_LIMIT = 10;
const WINDOW_MS = 60_000;
const SOURCES = new Set(Object.keys(report.sources));

const normalize = (q: string) => q.trim().toLowerCase().replace(/\s+/g, " ");
const presets = new Map((examples as Example[]).map((e) => [normalize(e.query), e]));

// Per-instance memory: each serverless instance counts on its own.
const hits = new Map<string, number[]>();

function rateLimited(ip: string): boolean {
  const now = Date.now();
  const recent = (hits.get(ip) ?? []).filter((t) => now - t < WINDOW_MS);
  const limited = recent.length >= RATE_LIMIT;
  if (!limited) recent.push(now);
  hits.set(ip, recent);
  return limited;
}

function clientIp(req: Request): string {
  return req.headers.get("x-forwarded-for")?.split(",")[0].trim() || req.headers.get("x-real-ip") || "local";
}

async function embedQuery(q: string): Promise<number[]> {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:embedContent`,
    {
      method: "POST",
      headers: { "content-type": "application/json", "x-goog-api-key": process.env.GOOGLE_API_KEY ?? "" },
      body: JSON.stringify({ content: { parts: [{ text: `task: search result | query: ${q}` }] } }),
    },
  );
  if (!res.ok) {
    throw new Error(res.status === 429 ? "the free embedding quota is used up" : `embedding failed (${res.status})`);
  }
  const data = (await res.json()) as { embedding: { values: number[] } };
  return data.embedding.values;
}

async function searchQdrant(vector: number[], source?: string): Promise<SearchResult[]> {
  const qdrant = new QdrantClient({
    url: process.env.QDRANT_URL,
    apiKey: process.env.QDRANT_API_KEY,
    checkCompatibility: false,
  });
  const { points } = await qdrant.query(COLLECTION, {
    query: vector,
    limit: 5,
    filter: source ? { must: [{ key: "source", match: { value: source } }] } : undefined,
    with_payload: true,
  });
  return points.map((p) => {
    const payload = p.payload as Omit<SearchResult, "score">;
    return {
      score: Math.round(p.score * 10_000) / 10_000,
      title: payload.title,
      section: payload.section,
      url: payload.url,
      source: payload.source,
      text: payload.text,
      doc_id: payload.doc_id,
      chunk_index: payload.chunk_index,
    };
  });
}

/** The preset query sharing the most words with q, used when live search is down. */
function closestPreset(q: string): Example {
  const words = new Set(normalize(q).split(" "));
  const overlap = (e: Example) => e.query.split(" ").filter((w) => words.has(w)).length;
  return (examples as Example[]).reduce((best, e) => (overlap(e) > overlap(best) ? e : best));
}

export async function POST(req: Request) {
  let body: { q?: unknown; source?: unknown };
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "Send JSON like {\"q\": \"...\"}." }, { status: 400 });
  }
  const q = typeof body.q === "string" ? body.q.trim() : "";
  const source = typeof body.source === "string" && body.source ? body.source : undefined;
  if (q.length < 1 || q.length > 200) {
    return Response.json({ error: "The query must be 1–200 characters." }, { status: 400 });
  }
  if (source && !SOURCES.has(source)) {
    return Response.json({ error: `Unknown source '${source}'.` }, { status: 400 });
  }

  const preset = presets.get(normalize(q));
  if (preset && !source) {
    return Response.json({ query: q, results: preset.results, cached: true });
  }

  if (rateLimited(clientIp(req))) {
    return Response.json(
      { error: "Too many searches: the limit is 10 per minute. Preset queries still work; otherwise wait a minute." },
      { status: 429, headers: { "retry-after": "60" } },
    );
  }

  try {
    const results = await searchQdrant(await embedQuery(q), source);
    return Response.json({ query: q, source, results, cached: false });
  } catch (err) {
    const fallback = closestPreset(q);
    const reason = err instanceof Error ? err.message : "upstream error";
    return Response.json({
      query: q,
      source,
      results: fallback.results,
      cached: true,
      notice: `Live search is unavailable right now (${reason}). Showing cached results for "${fallback.query}".`,
    });
  }
}
