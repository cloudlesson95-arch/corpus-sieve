import examples from "../../public/examples.json";
import report from "../../public/report.json";
import { SearchClient } from "@/components/search-client";
import type { Example } from "@/lib/types";

export default function SearchPage() {
  const sources = Object.entries(report.sources)
    .filter(([, counts]) => counts.kept > 0)
    .map(([name]) => name);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Search the cleaned corpus</h1>
        <p className="mt-1 max-w-3xl text-ink-2">
          {report.totals.kept} documents passed the quality checks and were chunked, embedded with Google&apos;s
          gemini-embedding-2 and stored in Qdrant. Search runs a cosine similarity query over{" "}
          {report.chunks?.count ?? "the"} chunks, optionally filtered by source.
        </p>
      </div>
      <SearchClient presets={examples as Example[]} sources={sources} />
    </div>
  );
}
