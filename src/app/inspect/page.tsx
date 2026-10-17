import type { Metadata } from "next";
import { InspectClient } from "@/components/inspect-client";
import boilerplate from "../../../data/raw/synthetic-boilerplate.json";
import htmlLitter from "../../../data/raw/synthetic-html-litter.json";
import mojibake from "../../../data/raw/synthetic-mojibake.json";
import nonEnglish from "../../../data/raw/synthetic-non-english.json";
import pii from "../../../data/raw/synthetic-pii.json";
import replacement from "../../../data/raw/synthetic-replacement-chars.json";

export const metadata: Metadata = { title: "Inspect a document · Corpus Sieve" };

// The pipeline's own synthetic problem documents (data/raw), each under 2,000 characters.
const EXAMPLES = [mojibake, htmlLitter, boilerplate, nonEnglish, pii, replacement].map((d) => ({
  title: d.title,
  text: d.text,
}));

export default function InspectPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Inspect a document</h1>
        <p className="mt-1 max-w-3xl text-ink-2">
          Paste up to 2,000 characters. A Python function runs the pipeline&apos;s own cleaning steps, per-document
          checks and chunker on it, without embedding or storing anything. Duplicate checks need the whole
          corpus, so they don&apos;t run here.
        </p>
      </div>
      <InspectClient examples={EXAMPLES} />
    </div>
  );
}
