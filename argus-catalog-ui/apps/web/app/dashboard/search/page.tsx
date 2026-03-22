"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Database, Loader2, Search } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { DashboardHeader } from "@/components/dashboard-header"
import { hybridSearch, type SemanticSearchResult } from "@/features/datasets/api"

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

function MatchBadge({ type }: { type: string }) {
  if (type === "hybrid") return <Badge variant="outline" className="text-[10px] px-1 py-0 text-purple-600 border-purple-200">hybrid</Badge>
  if (type === "semantic") return <Badge variant="outline" className="text-[10px] px-1 py-0 text-blue-600 border-blue-200">semantic</Badge>
  return <Badge variant="outline" className="text-[10px] px-1 py-0">keyword</Badge>
}

export default function SearchPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const q = searchParams.get("q") ?? ""

  const [results, setResults] = useState<SemanticSearchResult[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [provider, setProvider] = useState<string | null>(null)
  const [model, setModel] = useState<string | null>(null)

  const doSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([])
      setTotal(0)
      return
    }
    setIsLoading(true)
    try {
      const resp = await hybridSearch(searchQuery.trim(), 50, 0.3, 0.7)
      setResults(resp.items)
      setTotal(resp.total)
      setProvider(resp.provider)
      setModel(resp.model)
    } catch {
      setResults([])
      setTotal(0)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (q) {
      doSearch(q)
    } else {
      // No query (e.g. browser back) — go back to previous page
      router.back()
    }
  }, [q, doSearch, router])

  return (
    <>
      <DashboardHeader title="Search Results" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Search meta */}
        {!isLoading && q && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{total} result{total !== 1 ? "s" : ""} for &ldquo;{q}&rdquo;</span>
            {provider ? (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">{provider}/{model}</Badge>
            ) : (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">keyword only</Badge>
            )}
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Searching...</span>
          </div>
        )}

        {/* No results */}
        {!isLoading && q && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <Search className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              No datasets found matching &ldquo;{q}&rdquo;
            </p>
          </div>
        )}

        {/* Results */}
        {!isLoading && results.length > 0 && (
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/60">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Dataset</th>
                  <th className="px-3 py-2 text-left font-medium w-36">Platform</th>
                  <th className="px-3 py-2 text-center font-medium w-20">Origin</th>
                  <th className="px-3 py-2 text-center font-medium w-16">Fields</th>
                  <th className="px-3 py-2 text-center font-medium w-16">Tags</th>
                  <th className="px-3 py-2 text-center font-medium w-20">Match</th>
                  <th className="px-3 py-2 text-center font-medium w-20">Score</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {results.map((r) => (
                  <tr
                    key={r.dataset.id}
                    className="hover:bg-muted/30 cursor-pointer"
                    onClick={() => router.push(`/dashboard/datasets/${r.dataset.id}`)}
                  >
                    <td className="px-3 py-2.5">
                      <div className="font-medium">{r.dataset.name}</div>
                      {r.dataset.description && (
                        <p className="text-xs text-muted-foreground truncate max-w-[500px]">
                          {r.dataset.description}
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Database className="h-3 w-3" />
                        {r.dataset.platform_name}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <Badge variant="outline" className="text-xs">{r.dataset.origin}</Badge>
                    </td>
                    <td className="px-3 py-2.5 text-center text-muted-foreground">{r.dataset.schema_field_count}</td>
                    <td className="px-3 py-2.5 text-center text-muted-foreground">{r.dataset.tag_count}</td>
                    <td className="px-3 py-2.5 text-center"><MatchBadge type={r.match_type} /></td>
                    <td className="px-3 py-2.5 text-center">
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${scoreBg(r.score)} ${scoreColor(r.score)}`}>
                        {(r.score * 100).toFixed(0)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
