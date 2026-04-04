"use client"

import React, { useCallback, useMemo, useState } from "react"
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  Loader2,
  Rows3,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@workspace/ui/components/tooltip"
import type { QueryResult } from "../types"
import { useSql } from "./sql-provider"

// ---------------------------------------------------------------------------
// Result Panel (below the editor)
// ---------------------------------------------------------------------------

export function ResultPanel() {
  const { tabs, activeTabId, isExecuting } = useSql()
  const activeTab = tabs.find((t) => t.id === activeTabId)
  const result = activeTab?.result ?? null

  if (isExecuting) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Executing query...
      </div>
    )
  }

  if (!result) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Run a query to see results
      </div>
    )
  }

  if (result.status === "FAILED") {
    return (
      <div className="flex h-full flex-col p-4">
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-sm font-medium">Query Failed</span>
        </div>
        <pre className="mt-2 whitespace-pre-wrap rounded-md bg-destructive/5 p-3 text-xs text-destructive">
          {result.error_message || "Unknown error"}
        </pre>
      </div>
    )
  }

  return <ResultTable result={result} />
}

// ---------------------------------------------------------------------------
// Result data table
// ---------------------------------------------------------------------------

type SortConfig = {
  columnIndex: number
  direction: "asc" | "desc"
} | null

function ResultTable({ result }: { result: QueryResult }) {
  const [sort, setSort] = useState<SortConfig>(null)

  const sortedRows = useMemo(() => {
    if (!sort) return result.rows
    const { columnIndex, direction } = sort
    return [...result.rows].sort((a, b) => {
      const av = a[columnIndex]
      const bv = b[columnIndex]
      if (av === null || av === undefined) return 1
      if (bv === null || bv === undefined) return -1
      if (typeof av === "number" && typeof bv === "number") {
        return direction === "asc" ? av - bv : bv - av
      }
      const as = String(av)
      const bs = String(bv)
      return direction === "asc" ? as.localeCompare(bs) : bs.localeCompare(as)
    })
  }, [result.rows, sort])

  const toggleSort = useCallback(
    (colIndex: number) => {
      setSort((prev) => {
        if (prev?.columnIndex === colIndex) {
          if (prev.direction === "asc") return { columnIndex: colIndex, direction: "desc" }
          return null // remove sort
        }
        return { columnIndex: colIndex, direction: "asc" }
      })
    },
    [],
  )

  const handleDownloadCsv = useCallback(() => {
    const headers = result.columns.map((c) => c.name).join(",")
    const rows = result.rows
      .map((row) =>
        row
          .map((v) => {
            if (v === null || v === undefined) return ""
            const s = String(v)
            return s.includes(",") || s.includes('"') || s.includes("\n")
              ? `"${s.replace(/"/g, '""')}"`
              : s
          })
          .join(","),
      )
      .join("\n")
    const csv = `${headers}\n${rows}`
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "query_result.csv"
    a.click()
    URL.revokeObjectURL(url)
  }, [result])

  const handleCopyRow = useCallback(
    (rowIndex: number) => {
      const row = result.rows[rowIndex]
      if (!row) return
      const text = result.columns
        .map((col, i) => `${col.name}: ${row[i] ?? "NULL"}`)
        .join("\n")
      navigator.clipboard.writeText(text)
    },
    [result],
  )

  return (
    <div className="flex h-full flex-col">
      {/* Status bar */}
      <div className="flex items-center gap-3 border-b px-3 py-1.5">
        <div className="flex items-center gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          <span className="text-xs font-medium">Success</span>
        </div>
        <Badge variant="outline" className="gap-1 text-[10px]">
          <Rows3 className="h-3 w-3" />
          {result.row_count.toLocaleString()} rows
        </Badge>
        <Badge variant="outline" className="gap-1 text-[10px]">
          <Clock className="h-3 w-3" />
          {result.elapsed_ms < 1000
            ? `${result.elapsed_ms}ms`
            : `${(result.elapsed_ms / 1000).toFixed(1)}s`}
        </Badge>
        {result.has_more && (
          <Badge variant="outline" className="text-[10px] text-amber-600">
            Truncated
          </Badge>
        )}
        <div className="flex-1" />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleDownloadCsv}>
              <Download className="h-3.5 w-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Download CSV</TooltipContent>
        </Tooltip>
      </div>

      {/* Data grid */}
      <div className="flex-1 overflow-auto">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm">
              <tr>
                <th className="w-10 px-2 py-1.5 text-right text-muted-foreground">#</th>
                {result.columns.map((col, i) => (
                  <th
                    key={i}
                    className="cursor-pointer select-none px-3 py-1.5 text-left font-medium hover:bg-muted"
                    onClick={() => toggleSort(i)}
                  >
                    <div className="flex items-center gap-1">
                      <span>{col.name}</span>
                      <span className="text-[10px] text-muted-foreground">{col.data_type}</span>
                      {sort?.columnIndex === i && (
                        sort.direction === "asc" ? (
                          <ArrowUp className="h-3 w-3" />
                        ) : (
                          <ArrowDown className="h-3 w-3" />
                        )
                      )}
                    </div>
                  </th>
                ))}
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row, ri) => (
                <tr
                  key={ri}
                  className="border-b border-muted/30 hover:bg-muted/20"
                >
                  <td className="px-2 py-1 text-right text-muted-foreground">{ri + 1}</td>
                  {row.map((cell, ci) => (
                    <td key={ci} className="max-w-[300px] truncate px-3 py-1">
                      {cell === null || cell === undefined ? (
                        <span className="rounded bg-muted px-1 py-0.5 text-[10px] text-muted-foreground">
                          NULL
                        </span>
                      ) : typeof cell === "object" ? (
                        <span className="font-mono text-[11px]">{JSON.stringify(cell)}</span>
                      ) : (
                        String(cell)
                      )}
                    </td>
                  ))}
                  <td className="px-1">
                    <button
                      onClick={() => handleCopyRow(ri)}
                      className="rounded p-0.5 opacity-0 hover:bg-muted group-hover:opacity-100 [tr:hover_&]:opacity-100"
                    >
                      <Copy className="h-3 w-3 text-muted-foreground" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
