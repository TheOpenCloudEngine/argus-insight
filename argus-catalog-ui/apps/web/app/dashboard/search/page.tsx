"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { Database, Search, ArrowLeft } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { DashboardHeader } from "@/components/dashboard-header"
import type { DatasetSummary } from "@/features/datasets/data/schema"

const BASE = "/api/v1/catalog"

type SearchResult = {
  items: DatasetSummary[]
  total: number
  page: number
  page_size: number
}

async function searchDatasets(
  query: string,
  page: number = 1,
  pageSize: number = 50,
): Promise<SearchResult> {
  const params = new URLSearchParams({
    search: query,
    page: String(page),
    page_size: String(pageSize),
  })
  const res = await fetch(`${BASE}/datasets?${params}`)
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  inactive: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
  deprecated: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  removed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
}

export default function SearchPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const q = searchParams.get("q") ?? ""

  const [query, setQuery] = useState(q)
  const [results, setResults] = useState<DatasetSummary[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(false)

  const doSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([])
      setTotal(0)
      return
    }
    setIsLoading(true)
    try {
      const data = await searchDatasets(searchQuery.trim())
      setResults(data.items)
      setTotal(data.total)
    } catch {
      setResults([])
      setTotal(0)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (q) {
      setQuery(q)
      doSearch(q)
    }
  }, [q, doSearch])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && query.trim()) {
      router.push(`/dashboard/search?q=${encodeURIComponent(query.trim())}`)
    }
  }

  return (
    <>
      <DashboardHeader title="Search Results" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Search bar */}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="h-9 w-9" asChild>
            <Link href="/dashboard/datasets">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div className="relative flex-1 max-w-xl">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search dataset..."
              className="pl-8 h-9 text-sm"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
            />
          </div>
          {!isLoading && q && (
            <span className="text-sm text-muted-foreground">
              {total} result{total !== 1 ? "s" : ""} for &ldquo;{q}&rdquo;
            </span>
          )}
        </div>

        {/* Loading */}
        {isLoading && (
          <p className="text-sm text-muted-foreground text-center py-8">Searching...</p>
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
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {results.map((ds) => (
              <Link key={ds.id} href={`/dashboard/datasets/${ds.id}`}>
                <Card className="h-full transition-colors hover:bg-muted cursor-pointer">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-sm font-medium leading-snug line-clamp-1">
                        {ds.name}
                      </CardTitle>
                      <Badge
                        variant="outline"
                        className={`shrink-0 text-xs ${STATUS_COLORS[ds.status] ?? ""}`}
                      >
                        {ds.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0 space-y-2">
                    {ds.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {ds.description}
                      </p>
                    )}
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Database className="h-3 w-3" />
                        {ds.platform_name}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {ds.origin}
                      </Badge>
                      {ds.schema_field_count > 0 && (
                        <span>{ds.schema_field_count} fields</span>
                      )}
                      {ds.tag_count > 0 && (
                        <span>{ds.tag_count} tags</span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
