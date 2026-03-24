"use client";

import { useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { searchHybrid, type SearchHit, type SearchResult } from "@/lib/api";

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
        q: query,
        threshold,
        keyword_weight: kwWeight,
        semantic_weight: semWeight,
        limit: 20,
      });
      setResults(res.results);
      setTotal(res.total);
    } catch {
      setResults([]);
      setTotal(0);
    }
    setElapsed(Math.round(performance.now() - start));
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Search Playground</h1>

      {/* Search bar */}
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <SearchIcon className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Search across all collections..."
            className="w-full border rounded-md pl-10 pr-3 py-2 text-sm"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm disabled:opacity-50"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      {/* Options */}
      <div className="flex gap-4 text-xs text-gray-500">
        <label>
          Threshold:{" "}
          <input
            type="number"
            step="0.1"
            min="0"
            max="1"
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="w-16 border rounded px-1 py-0.5"
          />
        </label>
        <label>
          Keyword weight:{" "}
          <input
            type="number"
            step="0.1"
            min="0"
            max="1"
            value={kwWeight}
            onChange={(e) => setKwWeight(Number(e.target.value))}
            className="w-16 border rounded px-1 py-0.5"
          />
        </label>
        <label>
          Semantic weight:{" "}
          <input
            type="number"
            step="0.1"
            min="0"
            max="1"
            value={semWeight}
            onChange={(e) => setSemWeight(Number(e.target.value))}
            className="w-16 border rounded px-1 py-0.5"
          />
        </label>
      </div>

      {/* Results */}
      {total > 0 && (
        <p className="text-sm text-gray-500">
          {total} results ({elapsed}ms)
        </p>
      )}
      <div className="space-y-3">
        {results.map((hit, idx) => (
          <div key={idx} className="border rounded-lg p-4 space-y-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                  {hit.collection_name}
                </span>
                <span className="font-medium text-sm">
                  {hit.title || hit.external_id}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span
                  className={`px-1.5 py-0.5 rounded ${
                    hit.match_type === "hybrid"
                      ? "bg-purple-100 text-purple-700"
                      : hit.match_type === "semantic"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-700"
                  }`}
                >
                  {hit.match_type}
                </span>
                <span className="font-mono">{hit.similarity.toFixed(4)}</span>
              </div>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap line-clamp-3">
              {hit.chunk_text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
