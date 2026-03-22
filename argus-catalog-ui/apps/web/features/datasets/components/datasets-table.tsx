"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import {
  type ColumnFiltersState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { Brain, Loader2, Search, X } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import { DataTablePagination, DataTableFacetedFilter } from "@/components/data-table"
import { fetchPlatforms, hybridSearch, type SemanticSearchResult } from "../api"
import { type DatasetSummary, type Platform } from "../data/schema"
import { datasetsColumns as columns } from "./datasets-columns"
import { DatasetsPrimaryButtons } from "./datasets-primary-buttons"
import { useDatasets } from "./datasets-provider"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type DatasetsTableProps = {
  data: DatasetSummary[]
  isLoading?: boolean
}

export function DatasetsTable({ data, isLoading }: DatasetsTableProps) {
  const router = useRouter()
  const { total, page, pageSize, setPage, setPageSize } = useDatasets()

  const [sorting, setSorting] = useState<SortingState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [platforms, setPlatforms] = useState<Platform[]>([])

  // Hybrid search state
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<SemanticSearchResult[] | null>(null)
  const [searchMeta, setSearchMeta] = useState<{ provider: string | null; model: string | null } | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  useEffect(() => {
    fetchPlatforms().then(setPlatforms).catch(() => {})
  }, [])

  const platformOptions = useMemo(
    () => platforms.map((p) => ({ label: p.name, value: p.platform_id })),
    [platforms]
  )

  const statusOptions = [
    { label: "Active", value: "active" },
    { label: "Inactive", value: "inactive" },
    { label: "Deprecated", value: "deprecated" },
  ]

  const pageCount = useMemo(() => Math.ceil(total / pageSize), [total, pageSize])

  const table = useReactTable({
    data,
    columns,
    pageCount,
    state: {
      sorting,
      pagination: { pageIndex: page - 1, pageSize },
      columnFilters,
      columnVisibility,
    },
    manualPagination: true,
    manualFiltering: true,
    onPaginationChange: (updater) => {
      const next =
        typeof updater === "function"
          ? updater({ pageIndex: page - 1, pageSize })
          : updater
      if (next.pageSize !== pageSize) {
        setPageSize(next.pageSize)
      } else {
        setPage(next.pageIndex + 1)
      }
    },
    onColumnFiltersChange: setColumnFilters,
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  // Hybrid search handler
  const handleSearch = useCallback(async () => {
    const q = searchQuery.trim()
    if (!q) return
    setSearching(true)
    setSearchError(null)
    try {
      const resp = await hybridSearch(q, 50, 0.3, 0.7)
      setSearchResults(resp.items)
      setSearchMeta({ provider: resp.provider, model: resp.model })
    } catch (e) {
      setSearchError(e instanceof Error ? e.message : "Search failed")
      setSearchResults(null)
    } finally {
      setSearching(false)
    }
  }, [searchQuery])

  const handleClear = useCallback(() => {
    setSearchQuery("")
    setSearchResults(null)
    setSearchMeta(null)
    setSearchError(null)
  }, [])

  const isSearchActive = searchResults !== null

  return (
    <div className={cn("flex flex-1 flex-col gap-4")}>
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-2">
        {/* Left: Search bar + filters */}
        <div className="flex flex-1 items-center gap-2">
          {/* Hybrid search input */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search datasets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="h-8 w-[180px] lg:w-[280px] pl-7"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSearch}
            disabled={searching || !searchQuery.trim()}
            className="h-8 px-2"
          >
            {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          </Button>

          {/* Brain indicator */}
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center">
                <Brain className={`h-4 w-4 ${searchMeta?.provider ? "text-purple-500" : "text-muted-foreground/40"}`} />
              </div>
            </TooltipTrigger>
            <TooltipContent>
              {searchMeta?.provider
                ? `Semantic search active (${searchMeta.provider}/${searchMeta.model})`
                : "Semantic search — search to activate"
              }
            </TooltipContent>
          </Tooltip>

          {/* Clear */}
          {isSearchActive && (
            <Button variant="ghost" size="sm" onClick={handleClear} className="h-8 px-2">
              <X className="h-4 w-4 mr-1" />Clear
            </Button>
          )}

          {/* Faceted filters (hidden during search) */}
          {!isSearchActive && (
            <>
              {(() => { const c = table.getColumn("platform_name"); return c ? <DataTableFacetedFilter column={c} title="Platform" options={platformOptions} /> : null })()}
              {(() => { const c = table.getColumn("origin"); return c ? <DataTableFacetedFilter column={c} title="Environment" options={[{ label: "PROD", value: "PROD" }, { label: "DEV", value: "DEV" }, { label: "STAGING", value: "STAGING" }]} /> : null })()}
              {(() => { const c = table.getColumn("status"); return c ? <DataTableFacetedFilter column={c} title="Status" options={statusOptions} /> : null })()}
            </>
          )}
        </div>

        {/* Right: Primary buttons */}
        <DatasetsPrimaryButtons />
      </div>

      {/* Error */}
      {searchError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {searchError}
        </div>
      )}

      {/* Search results view */}
      {isSearchActive ? (
        <>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>{searchResults.length} results for &quot;{searchQuery}&quot;</span>
            {searchMeta?.provider ? (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">{searchMeta.provider}/{searchMeta.model}</Badge>
            ) : (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">keyword only</Badge>
            )}
          </div>

          <div className="overflow-hidden rounded-md border">
            {searchResults.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Dataset</TableHead>
                    <TableHead className="w-32">Platform</TableHead>
                    <TableHead className="w-20 text-center">Origin</TableHead>
                    <TableHead className="w-16 text-center">Tags</TableHead>
                    <TableHead className="w-20 text-center">Match</TableHead>
                    <TableHead className="w-20 text-center">Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {searchResults.map((r) => (
                    <TableRow
                      key={r.dataset.id}
                      className="cursor-pointer"
                      onClick={() => router.push(`/dashboard/datasets/${r.dataset.id}`)}
                    >
                      <TableCell>
                        <div className="font-medium text-sm">{r.dataset.name}</div>
                        {r.dataset.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-[500px]">{r.dataset.description}</p>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">{r.dataset.platform_name}</TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className="text-xs">{r.dataset.origin}</Badge>
                      </TableCell>
                      <TableCell className="text-center text-muted-foreground">{r.dataset.tag_count}</TableCell>
                      <TableCell className="text-center"><MatchBadge type={r.match_type} /></TableCell>
                      <TableCell className="text-center">
                        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${scoreBg(r.score)} ${scoreColor(r.score)}`}>
                          {(r.score * 100).toFixed(0)}%
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="h-24 flex items-center justify-center text-muted-foreground">
                No matching datasets found.
              </div>
            )}
          </div>
        </>
      ) : (
        /* Normal paginated table */
        <>
          <div className="overflow-hidden rounded-md border">
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id} className="group/row">
                    {headerGroup.headers.map((header) => (
                      <TableHead
                        key={header.id}
                        colSpan={header.colSpan}
                        className={cn(
                          "bg-background group-hover/row:bg-muted",
                          (header.column.columnDef.meta as { className?: string })?.className
                        )}
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={columns.length} className="h-24 text-center">
                      <p className="text-muted-foreground">Loading datasets...</p>
                    </TableCell>
                  </TableRow>
                ) : table.getRowModel().rows?.length ? (
                  table.getRowModel().rows.map((row) => (
                    <TableRow key={row.id} className="group/row">
                      {row.getVisibleCells().map((cell) => (
                        <TableCell
                          key={cell.id}
                          className={cn(
                            "bg-background group-hover/row:bg-muted",
                            (cell.column.columnDef.meta as { className?: string })?.className
                          )}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={columns.length} className="h-24 text-center">
                      No datasets found.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          <DataTablePagination table={table} className="mt-auto" />
        </>
      )}
    </div>
  )
}
