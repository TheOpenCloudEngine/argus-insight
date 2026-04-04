"use client"

import React, { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  History,
  Loader2,
  Rows3,
  Square,
  Table2,
} from "lucide-react"
import { AgGridReact } from "ag-grid-react"
import { AllCommunityModule, ModuleRegistry, type ColDef } from "ag-grid-community"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@workspace/ui/components/tooltip"
import type { QueryResult, QueryHistoryItem } from "../types"
import * as api from "../api"
import { useSql } from "./sql-provider"

ModuleRegistry.registerModules([AllCommunityModule])

// ---------------------------------------------------------------------------
// Result Panel (AG Grid result + Query History tabs)
// ---------------------------------------------------------------------------

export function ResultPanel() {
  const { tabs, activeTabId, isExecuting } = useSql()
  const activeTab = tabs.find((t) => t.id === activeTabId)
  const result = activeTab?.result ?? null
  const [activePanel, setActivePanel] = useState<"result" | "history">("result")

  return (
    <div className="flex h-full flex-col">
      {/* Tab bar */}
      <div className="flex items-center border-b px-2">
        <div role="tablist" className="flex items-center gap-0">
          <button
            role="tab"
            aria-selected={activePanel === "result"}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border-b-2 transition-colors ${
              activePanel === "result"
                ? "border-primary text-foreground font-medium"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setActivePanel("result")}
          >
            <Table2 className="h-3.5 w-3.5" /> Result
          </button>
          <button
            role="tab"
            aria-selected={activePanel === "history"}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border-b-2 transition-colors ${
              activePanel === "history"
                ? "border-primary text-foreground font-medium"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setActivePanel("history")}
          >
            <History className="h-3.5 w-3.5" /> Query History
          </button>
        </div>

        {/* Result status badges */}
        {activePanel === "result" && result && result.status !== "FAILED" && (
          <div className="flex items-center gap-2 ml-4">
            <div className="flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-green-500" />
              <span className="text-xs font-medium">Success</span>
            </div>
            <Badge variant="outline" className="gap-1 text-xs">
              <Rows3 className="h-2.5 w-2.5" />
              {result.row_count.toLocaleString()} rows
            </Badge>
            <Badge variant="outline" className="gap-1 text-xs">
              <Clock className="h-2.5 w-2.5" />
              {result.elapsed_ms < 1000
                ? `${result.elapsed_ms}ms`
                : `${(result.elapsed_ms / 1000).toFixed(1)}s`}
            </Badge>
            {result.total_pages > 1 && (
              <Badge variant="outline" className="text-xs">
                Page {result.page}/{result.total_pages}
              </Badge>
            )}
          </div>
        )}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0">
        {activePanel === "result" ? (
          <ResultGrid result={result} isExecuting={isExecuting} />
        ) : (
          <QueryHistoryGrid />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Result Grid (AG Grid)
// ---------------------------------------------------------------------------

function ResultGrid({ result, isExecuting }: { result: QueryResult | null; isExecuting: boolean }) {
  const { cancelExecution, fetchResultPage } = useSql()
  const columnDefs = useMemo<ColDef[]>(() => {
    if (!result || result.status === "FAILED") return []
    return result.columns.map((col, i) => ({
      headerName: col.name,
      field: String(i),
      sortable: true,
      resizable: true,
      minWidth: 100,
      headerTooltip: col.data_type,
      valueFormatter: (params: any) => {
        const v = params.value
        if (v === null || v === undefined) return "NULL"
        if (typeof v === "object") return JSON.stringify(v)
        return String(v)
      },
      cellStyle: (params: any) => {
        if (params.value === null || params.value === undefined) {
          return { color: "#9ca3af", fontStyle: "italic" }
        }
        return undefined
      },
    }))
  }, [result])

  const rowData = useMemo(() => {
    if (!result || result.status === "FAILED") return []
    return result.rows.map((row) => {
      const obj: Record<string, unknown> = {}
      row.forEach((v, i) => { obj[String(i)] = v })
      return obj
    })
  }, [result])

  const handleDownloadCsv = useCallback(() => {
    if (!result?.execution_id) return
    // Use streaming server-side export
    const url = api.getExportUrl(result.execution_id)
    const a = document.createElement("a")
    a.href = url
    a.download = "query_result.csv"
    a.click()
  }, [result])

  if (isExecuting) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Executing query...
        </div>
        <Button
          variant="destructive"
          size="sm"
          className="gap-1.5 text-xs"
          onClick={cancelExecution}
        >
          <Square className="h-3 w-3" />
          Cancel
        </Button>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-foreground">
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
        <pre className="mt-2 whitespace-pre-wrap rounded-md bg-destructive/5 p-3 text-xs text-destructive font-[D2Coding,monospace]">
          {result.error_message || "Unknown error"}
        </pre>
      </div>
    )
  }

  const currentPage = result.page ?? 1
  const totalPages = result.total_pages ?? 1
  const pageSize = result.page_size ?? 500
  const startRow = (currentPage - 1) * pageSize + 1
  const endRow = Math.min(startRow + result.rows.length - 1, result.row_count)

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar: pagination + export */}
      <div className="flex items-center px-2 py-1 border-b gap-2">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost" size="icon" className="h-6 w-6"
            disabled={currentPage <= 1}
            onClick={() => fetchResultPage(currentPage - 1)}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <span className="text-xs text-muted-foreground min-w-[120px] text-center">
            {startRow.toLocaleString()}-{endRow.toLocaleString()} of {result.row_count.toLocaleString()}
          </span>
          <Button
            variant="ghost" size="icon" className="h-6 w-6"
            disabled={currentPage >= totalPages}
            onClick={() => fetchResultPage(currentPage + 1)}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
          <span className="text-[10px] text-muted-foreground">
            Page {currentPage} / {totalPages}
          </span>
        </div>
        <div className="flex-1" />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleDownloadCsv}>
              <Download className="h-3.5 w-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Download all as CSV</TooltipContent>
        </Tooltip>
      </div>

      {/* AG Grid — no client-side pagination, server handles it */}
      <div className="ag-theme-alpine flex-1" style={{ width: "100%" }}>
        <style>{`
          .ag-theme-alpine {
            --ag-font-family: 'Roboto Condensed', Roboto, sans-serif;
            --ag-font-size: var(--text-sm);
          }
        `}</style>
        <AgGridReact
          columnDefs={columnDefs}
          rowData={rowData}
          headerHeight={32}
          rowHeight={30}
          defaultColDef={{
            sortable: true,
            resizable: true,
            filter: true,
          }}
          suppressCellFocus
          animateRows={false}
          onFirstDataRendered={(params) => {
            params.api.autoSizeAllColumns()
          }}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Query History Grid (AG Grid)
// ---------------------------------------------------------------------------

function QueryHistoryGrid() {
  const { datasources, workspaceDatasources, updateTabSql, activeTabId, updateTabDatasource } = useSql()
  const [history, setHistory] = useState<QueryHistoryItem[]>([])
  const [loading, setLoading] = useState(false)

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.fetchQueryHistory({ pageSize: 200 })
      setHistory(data.items)
    } catch {
      setHistory([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  const columnDefs = useMemo<ColDef[]>(() => [
    {
      headerName: "Status",
      field: "status",
      width: 90,
      cellStyle: (params: any) => {
        if (params.value === "FINISHED") return { color: "#16a34a", fontWeight: 600 }
        if (params.value === "FAILED") return { color: "#dc2626", fontWeight: 600 }
        return { color: "#6b7280" }
      },
    },
    {
      headerName: "SQL",
      field: "sql_text",
      flex: 1,
      minWidth: 300,
      tooltipField: "sql_text",
    },
    {
      headerName: "Datasource",
      field: "datasource_name",
      width: 150,
    },
    {
      headerName: "Engine",
      field: "engine_type",
      width: 90,
      cellStyle: { textTransform: "uppercase", fontSize: "11px", fontWeight: 600 },
    },
    {
      headerName: "Rows",
      field: "row_count",
      width: 80,
      type: "numericColumn",
      valueFormatter: (p: any) => p.value != null ? p.value.toLocaleString() : "—",
    },
    {
      headerName: "Time",
      field: "elapsed_ms",
      width: 80,
      type: "numericColumn",
      valueFormatter: (p: any) => {
        if (p.value == null) return "—"
        return p.value < 1000 ? `${p.value}ms` : `${(p.value / 1000).toFixed(1)}s`
      },
    },
    {
      headerName: "Executed",
      field: "executed_at",
      width: 150,
      valueFormatter: (p: any) => {
        if (!p.value) return ""
        const d = new Date(p.value)
        const pad = (n: number) => String(n).padStart(2, "0")
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
      },
    },
  ], [])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading history...
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="ag-theme-alpine sql-history-grid flex-1" style={{ width: "100%" }}>
        <style>{`
          .sql-history-grid {
            --ag-font-family: 'Roboto Condensed', Roboto, sans-serif;
            --ag-font-size: var(--text-sm);
            --ag-wrapper-border-radius: 0;
            --ag-border-color: transparent;
            --ag-header-background-color: transparent;
          }
          .sql-history-grid .ag-root-wrapper {
            border: none;
          }
        `}</style>
        <AgGridReact
          columnDefs={columnDefs}
          rowData={history}
          headerHeight={32}
          rowHeight={30}
          defaultColDef={{
            sortable: true,
            resizable: true,
          }}
          suppressCellFocus
          onRowDoubleClicked={(event) => {
            // Double-click to load SQL into editor (keep existing datasource)
            const item = event.data as QueryHistoryItem
            if (item?.sql_text) {
              updateTabSql(activeTabId, item.sql_text)
            }
        }}
        pagination={true}
        paginationPageSize={50}
        paginationPageSizeSelector={[50, 100, 200]}
      />
      </div>
    </div>
  )
}
