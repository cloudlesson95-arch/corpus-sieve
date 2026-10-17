import type { Metadata } from "next";
import Link from "next/link";
import report from "../../public/report.json";
import "./globals.css";

export const metadata: Metadata = {
  title: "Corpus Sieve",
  description:
    "A document ingestion pipeline that cleans, validates, chunks and embeds documents into Qdrant, with search and a data-quality report.",
};

const NAV = [
  { href: "/", label: "Search" },
  { href: "/quality", label: "Data quality" },
  { href: "/inspect", label: "Inspect a document" },
];

const wikipediaArticles = report.documents
  .filter((d) => d.source !== "synthetic")
  .sort((a, b) => a.title.localeCompare(b.title));

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <header className="border-b border-line bg-surface">
          <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href="/" className="font-semibold">
              Corpus Sieve
            </Link>
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className="text-sm text-ink-2 hover:text-ink">
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t border-line bg-surface">
          <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-ink-2">
            <p>
              Article text comes from English Wikipedia and is licensed under{" "}
              <a className="underline" href="https://creativecommons.org/licenses/by-sa/4.0/">
                CC BY-SA 4.0
              </a>
              ; it was trimmed and cleaned by this pipeline. The synthetic test documents were written for
              this demo.
            </p>
            <details className="mt-2">
              <summary className="cursor-pointer">The {wikipediaArticles.length} Wikipedia articles</summary>
              <ul className="mt-2 columns-1 gap-6 sm:columns-2 md:columns-3">
                {wikipediaArticles.map((d) => (
                  <li key={d.id}>
                    <a className="underline decoration-line hover:decoration-ink-2" href={d.url}>
                      {d.title}
                    </a>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        </footer>
      </body>
    </html>
  );
}
