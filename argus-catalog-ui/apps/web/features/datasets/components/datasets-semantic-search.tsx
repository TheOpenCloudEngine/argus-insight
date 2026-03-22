"use client"

import { useCallback, useState } from "react"
import { useRouter } from "next/navigation"
import { Brain, Loader2, Search, X } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@workspace/ui/components/select"

import {
  semanticSearch, hybridSearch, type SemanticSearchResult, type SemanticSearchResponse,
} from "../api"

type SearchMode = "keyword" | "semantic" | "hybrid"

export function DatasetsSemanticSearch({
  onClose,
}: {
  onClose: () => void
}) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [mode, setMode] = useState<SearchMode>("hybrid")
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<SemanticSearchResult[] | null>(null)
  const [meta, setMeta] = useState<{ provider: string | null; model: string | null; total: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      let resp: SemanticSearchResponse
      if (mode === "semantic") {
        resp = await semanticSearch(query, 20, 0.2)
      } else {
        resp = await hybridSearch(query, 20, 0.3, 0.7)
      }
      setResults(resp.items)
      setMeta({ provider: resp.provider, model: resp.model, total: resp.total })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed")
      setResults(null)
    } finally {
      setLoading(false)
    }
  }, [query, mode])

  function scoreColor(score: number): string {
    if (score >= 0.8) return "text-emerald-600"
    if (score >= 0.6) return "text-blue-600"
    if (score >= 0.4) return "text-amber-600"
    return "text-muted-foreground"
  }

  function scoreBg(score: number): string {
    if (score >= 0.8) return "bg-emerald-50 border-emerald-200"
    if (score >= 0.6) return "bg-blue-50 border-blue-200"
    if (score >= 0.4) return "bg-amber-50 border-amber-200"
    return "bg-muted/50 border-muted"
  }

  return (
    <div className="space-y-3">
      {/* Search bar */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Brain className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-purple-500" />
          <Input
            placeholder="Describe what you're looking for..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="pl-8 h-9"
          />
        </div>
        <Select value={mode} onValueChange={(v) => setMode(v as SearchMode)}>
          <SelectTrigger className="w-[130px] h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="hybrid">Hybrid</SelectItem>
            <SelectItem value="semantic">Semantic</SelectItem>
          </SelectContent>
        </Select>
        <Button size="sm" className="h-9" onClick={handleSearch} disabled={loading || !query.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        </Button>
        <Button variant="ghost" size="sm" className="h-9" onClick={onClose}>
          <X className="h-4 w-4 mr-1" />Close
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="space-y-2">
          {/* Meta */}
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>{meta?.total ?? 0} results</span>
            {meta?.provider && (
              <span>
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">{meta.provider}/{meta.model}</Badge>
              </span>
            )}
            <span>{mode === "hybrid" ? "Hybrid (keyword 30% + semantic 70%)" : "Semantic only"}</span>
          </div>

          {/* Result list */}
          {results.length > 0 ? (
            <div className="border rounded-md overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/60">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Dataset</th>
                    <th className="px-3 py-2 text-left font-medium w-32">Platform</th>
                    <th className="px-3 py-2 text-center font-medium w-20">Origin</th>
                    <th className="px-3 py-2 text-center font-medium w-16">Tags</th>
                    <th className="px-3 py-2 text-center font-medium w-20">Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {results.map((r, i) => (
                    <tr
                      key={r.dataset.id}
                      className="hover:bg-muted/30 cursor-pointer"
                      onClick={() => router.push(`/dashboard/datasets/${r.dataset.id}`)}
                    >
                      <td className="px-3 py-2">
                        <div className="font-medium text-sm">{r.dataset.name}</div>
                        {r.dataset.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-[500px]">
                            {r.dataset.description}
                          </p>
                        )}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground text-sm">{r.dataset.platform_name}</td>
                      <td className="px-3 py-2 text-center">
                        <Badge variant="outline" className="text-xs">{r.dataset.origin}</Badge>
                      </td>
                      <td className="px-3 py-2 text-center text-muted-foreground">{r.dataset.tag_count}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${scoreBg(r.score)} ${scoreColor(r.score)}`}>
                          {(r.score * 100).toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-sm text-muted-foreground">
              No matching datasets found. Try a different query or lower the threshold.
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!results && !loading && !error && (
        <div className="text-center py-12 text-muted-foreground">
          <Brain className="h-8 w-8 mx-auto mb-3 text-purple-300" />
          <p className="text-sm">Search datasets by meaning, not just keywords.</p>
          <p className="text-xs mt-1">Try: &quot;customer purchase history&quot;, &quot;daily sales aggregation&quot;</p>
        </div>
      )}
    </div>
  )
}
