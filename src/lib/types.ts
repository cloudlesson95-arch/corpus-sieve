export type SearchResult = {
  score: number;
  title: string;
  section: string;
  url: string;
  source: string;
  text: string;
  doc_id: string;
  chunk_index: number;
};

export type Example = { query: string; results: SearchResult[] };

export type SearchResponse = {
  query: string;
  source?: string;
  results: SearchResult[];
  cached: boolean;
  notice?: string;
  error?: string;
};
