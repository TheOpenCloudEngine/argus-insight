"use client";

import { useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { searchHybrid, type SearchHit } from "@/lib/api";

export default function SearchPlaygroundPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchHit[]>([]);
  const [total, setTotal] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [loading, setLoading] = useState(false);
  const [threshold, setThreshold] = useState(0.3);
  const [kwWeight, setKwWeight] = useState(0.3);
  const [semWeight, setSemWeight] = useState(0.7);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    const start = performance.now();
    try {
      const res = await searchHybrid({
        q: query, threshold,
        keyword_weight: kwWeight, semantic_weight: semWeight, limit: 20,
      });
      setResults(res.results);
      setTotal(res.total);
    } catch { setResults([]); setTotal(0); }
    setElapsed(Math.round(performance.now() - start));
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <SearchIcon className="absolute left-3 top-2.5 h-4 w-4 text-[var(--muted-foreground)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Search across all collections..."
            className="w-full rounded-[var(--radius)] border bg-transparent pl-10 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={loading}
          className="px-4 py-2 rounded-[var(--radius)] text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      {/* Options */}
      <div className="flex gap-4 text-xs text-[var(--muted-foreground)]">
        <label>Threshold: <input type="number" step="0.1" min="0" max="1" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} className="w-16 rounded border bg-transparent px-1.5 py-0.5" /></label>
        <label>Keyword: <input type="number" step="0.1" min="0" max="1" value={kwWeight} onChange={(e) => setKwWeight(Number(e.target.value))} className="w-16 rounded border bg-transparent px-1.5 py-0.5" /></label>
        <label>Semantic: <input type="number" step="0.1" min="0" max="1" value={semWeight} onChange={(e) => setSemWeight(Number(e.target.value))} className="w-16 rounded border bg-transparent px-1.5 py-0.5" /></label>
      </div>

      {total > 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">{total} results ({elapsed}ms)</p>
      )}

      {/* Results */}
      <div className="space-y-2">
        {results.map((hit, idx) => (
          <div key={idx} className="rounded-[var(--radius)] border p-4" style={{ background: "var(--card)" }}>
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}>
                  {hit.collection_name}
                </span>
                <span className="font-medium text-sm">{hit.title || hit.external_id}</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                <MatchBadge type={hit.match_type} />
                <span className="font-mono">{hit.similarity.toFixed(4)}</span>
              </div>
            </div>
            <p className="text-sm text-[var(--muted-foreground)] whitespace-pre-wrap line-clamp-3">
              {hit.chunk_text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function MatchBadge({ type }: { type: string }) {
  const s: Record<string, string> = {
    hybrid: "bg-violet-50 text-violet-700 border-violet-200",
    semantic: "bg-emerald-50 text-emerald-700 border-emerald-200",
    keyword: "bg-gray-50 text-gray-600 border-gray-200",
  };
  return <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${s[type] || s.keyword}`}>{type}</span>;
}
