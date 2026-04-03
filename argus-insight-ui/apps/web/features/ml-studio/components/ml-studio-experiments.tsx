"use client"

import { useEffect, useMemo, useState } from "react"
import {
  BarChart3,
  CheckCircle2,
  Clock,
  FlaskConical,
  Loader2,
  Trophy,
  XCircle,
} from "lucide-react"
import { AgGridReact } from "ag-grid-react"
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type PaginationNumberFormatterParams,
} from "ag-grid-community"
import { Badge } from "@workspace/ui/components/badge"
import { Card, CardContent } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"

import { authFetch } from "@/features/auth/auth-fetch"

ModuleRegistry.registerModules([AllCommunityModule])

// ── Types ─────────────────────────────────────────────────

interface TrainJob {
  id: number
  name: string
  status: string
  task_type: string
  target_column: string
  metric: string
  algorithm: string
  progress: number
  results: {
    leaderboard: { rank: number; model_name: string; metrics: Record<string, number>; training_time_seconds: number }[]
    best_model: { model_name: string; metrics: Record<string, number> } | null
    feature_importance: Record<string, number>
    metric_key: string
  } | null
  error_message: string | null
  author_username: string | null
  created_at: string
  completed_at: string | null
}

// ── Helpers ───────────────────────────────────────────────

function formatDateTime(value: string): string {
  const d = new Date(value)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const STATUS_CONFIG: Record<string, { label: string; color: string; fontColor: string }> = {
  pending: { label: "Pending", color: "bg-gray-100 text-gray-800", fontColor: "#9ca3af" },
  running: { label: "Running", color: "bg-blue-100 text-blue-800", fontColor: "#2563eb" },
  completed: { label: "Completed", color: "bg-green-100 text-green-800", fontColor: "#16a34a" },
  failed: { label: "Failed", color: "bg-red-100 text-red-800", fontColor: "#dc2626" },
  cancelled: { label: "Cancelled", color: "bg-orange-100 text-orange-800", fontColor: "#d97706" },
}

const TASK_LABELS: Record<string, string> = {
  classification: "Classification",
  regression: "Regression",
  timeseries: "Time Series",
}

// ── Component ─────────────────────────────────────────────

export function MLStudioExperiments() {
  const [jobs, setJobs] = useState<TrainJob[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedJob, setSelectedJob] = useState<TrainJob | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  useEffect(() => {
    async function load() {
      const stored = sessionStorage.getItem("argus_last_workspace_id")
      if (!stored) { setLoading(false); return }
      try {
        const res = await authFetch(
          `/api/v1/ml-studio/jobs?workspace_id=${stored}&page=1&page_size=50`,
        )
        if (res.ok) {
          const data = await res.json()
          setJobs(data.jobs ?? [])
        }
      } catch { /* ignore */ }
      finally { setLoading(false) }
    }
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleKill = async (jobId: number) => {
    try {
      await authFetch(`/api/v1/ml-studio/jobs/${jobId}`, { method: "DELETE" })
    } catch { /* ignore */ }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const columnDefs = useMemo<any[]>(
    () => [
      {
        headerName: "Experiment",
        field: "name",
        minWidth: 250,
        flex: 2,
        valueGetter: (params: any) => {
          if (!params.data) return ""
          return `${params.data.name}  (#${params.data.id})`
        },
      },
      {
        headerName: "Task",
        field: "task_type",
        width: 120,
        valueFormatter: (params: any) => TASK_LABELS[params.value] || params.value,
      },
      {
        headerName: "Target",
        field: "target_column",
        width: 130,
        cellStyle: { fontFamily: "D2Coding, monospace" },
      },
      {
        headerName: "Status",
        field: "status",
        width: 130,
        valueGetter: (params: any) => {
          if (!params.data) return ""
          const st = STATUS_CONFIG[params.data.status] || STATUS_CONFIG.pending!
          const pct = params.data.status === "running" ? ` ${params.data.progress}%` : ""
          return `${st.label}${pct}`
        },
        cellStyle: (params: any) => {
          const st = STATUS_CONFIG[params.data?.status]
          return st ? { color: st.fontColor, fontWeight: 500 } : {}
        },
      },
      {
        headerName: "Best Model",
        width: 140,
        valueGetter: (params: any) => params.data?.results?.best_model?.model_name || "—",
      },
      {
        headerName: "Score",
        width: 140,
        cellStyle: { textAlign: "right", fontFamily: "D2Coding, monospace" },
        valueGetter: (params: any) => {
          const best = params.data?.results?.best_model?.metrics
          if (!best) return "—"
          const entries = Object.entries(best)
          if (entries.length === 0) return "—"
          const [k, v] = entries[0]!
          return `${k}: ${(v as number).toFixed(4)}`
        },
      },
      {
        headerName: "Author",
        field: "author_username",
        width: 100,
      },
      {
        headerName: "Created",
        field: "created_at",
        width: 140,
        valueFormatter: (params: any) => params.value ? formatDateTime(params.value) : "",
      },
      {
        headerName: "Duration",
        width: 100,
        valueGetter: (params: any) => {
          if (!params.data) return ""
          const start = new Date(params.data.created_at).getTime()
          const end = params.data.completed_at
            ? new Date(params.data.completed_at).getTime()
            : (params.data.status === "running" || params.data.status === "pending" ? Date.now() : start)
          const sec = Math.floor((end - start) / 1000)
          if (sec < 60) return `${sec}s`
          if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`
          return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`
        },
      },
      {
        headerName: "",
        width: 70,
        sortable: false,
        filter: false,
        valueGetter: (params: any) => {
          if (!params.data) return ""
          return (params.data.status === "running" || params.data.status === "pending") ? "Kill" : ""
        },
        cellStyle: (params: any) => {
          if (params.data?.status === "running" || params.data?.status === "pending") {
            return { color: "#dc2626", cursor: "pointer", fontWeight: 500 }
          }
          return {}
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <FlaskConical className="h-10 w-10 mb-3 opacity-30" />
        <p className="text-sm">No experiments yet</p>
        <p className="text-xs mt-1">Start a new experiment from the Wizard tab</p>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col" style={{ minHeight: 0 }}>
      <div className="ag-theme-alpine flex-1" style={{ width: "100%" }}>
        <style>{`
          .ag-theme-alpine {
            --ag-font-family: 'Roboto Condensed', Roboto, sans-serif;
            --ag-font-size: var(--text-sm);
          }
        `}</style>
        <AgGridReact<TrainJob>
          rowData={jobs}
          columnDefs={columnDefs}
          loading={loading}
          rowSelection="single"
          overlayNoRowsTemplate="No experiments yet."
          onCellClicked={(event: any) => {
            if (!event.data) return
            // Kill column click
            if (event.colDef?.headerName === "" && (event.data.status === "running" || event.data.status === "pending")) {
              if (confirm(`Cancel job "${event.data.name}"?`)) {
                handleKill(event.data.id)
              }
              return
            }
            // Normal row click → open detail
            setSelectedJob(event.data)
            setDetailOpen(true)
          }}
          getRowId={(params) => String(params.data.id)}
          headerHeight={36}
          rowHeight={40}
          pagination={true}
          paginationPageSize={10}
          paginationPageSizeSelector={[10, 20, 50]}
          paginationNumberFormatter={(params: PaginationNumberFormatterParams) =>
            params.value.toLocaleString()
          }
        />
      </div>

      {/* Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="sm:max-w-[65vw] max-h-[65vh] overflow-y-auto">
          {selectedJob && (
            <>
              <DialogHeader>
                <DialogTitle className="text-sm flex items-center gap-2">
                  <FlaskConical className="h-4 w-4" />
                  {selectedJob.name}
                  <Badge className={`text-[10px] ${(STATUS_CONFIG[selectedJob.status] || STATUS_CONFIG.pending!).color}`}>
                    {(STATUS_CONFIG[selectedJob.status] || STATUS_CONFIG.pending!).label}
                  </Badge>
                </DialogTitle>
              </DialogHeader>

              <div className="space-y-4 text-sm">
                {/* Info */}
                <div className="grid grid-cols-4 gap-3">
                  <div>
                    <span className="text-xs text-muted-foreground">Task</span>
                    <p>{TASK_LABELS[selectedJob.task_type] || selectedJob.task_type}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Target</span>
                    <p className="font-mono">{selectedJob.target_column}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Metric</span>
                    <p>{selectedJob.metric}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Algorithm</span>
                    <p>{selectedJob.algorithm}</p>
                  </div>
                </div>

                {/* Progress */}
                {(selectedJob.status === "running" || selectedJob.status === "pending") && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Progress</span>
                      <span>{selectedJob.progress}%</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${selectedJob.progress}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Error */}
                {selectedJob.error_message && (
                  <p className="text-sm text-red-500">{selectedJob.error_message}</p>
                )}

                {/* Results */}
                {selectedJob.results && (
                  <>
                    <div className="grid gap-4 lg:grid-cols-2">
                      {selectedJob.results.best_model && (
                        <Card>
                          <CardContent className="pt-4">
                            <div className="flex items-center gap-2 mb-3">
                              <Trophy className="h-5 w-5 text-yellow-500" />
                              <span className="font-semibold">{selectedJob.results.best_model.model_name}</span>
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                              {Object.entries(selectedJob.results.best_model.metrics).map(([k, v]) => (
                                <div key={k} className="flex justify-between">
                                  <span className="text-muted-foreground">{k}</span>
                                  <span className="font-mono font-medium">{v.toFixed(4)}</span>
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}

                      {selectedJob.results.feature_importance && Object.keys(selectedJob.results.feature_importance).length > 0 && (
                        <Card>
                          <CardContent className="pt-4">
                            <p className="font-semibold mb-3 flex items-center gap-2">
                              <BarChart3 className="h-4 w-4" /> Feature Importance
                            </p>
                            <div className="space-y-2">
                              {Object.entries(selectedJob.results.feature_importance)
                                .sort(([, a], [, b]) => b - a)
                                .slice(0, 8)
                                .map(([name, value]) => (
                                  <div key={name} className="flex items-center gap-2">
                                    <span className="w-28 truncate text-xs">{name}</span>
                                    <div className="flex-1 h-3 rounded-full bg-muted">
                                      <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(value * 300, 100)}%` }} />
                                    </div>
                                    <span className="text-xs font-mono w-12 text-right">{(value * 100).toFixed(1)}%</span>
                                  </div>
                                ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </div>

                    {selectedJob.results.leaderboard.length > 0 && (
                      <div className="rounded-lg border">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead className="w-10 text-sm">#</TableHead>
                              <TableHead className="text-sm">Model</TableHead>
                              {Object.keys(selectedJob.results.leaderboard[0]!.metrics).map((k) => (
                                <TableHead key={k} className="text-right text-sm">{k}</TableHead>
                              ))}
                              <TableHead className="text-right text-sm">Time</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {selectedJob.results.leaderboard.map((entry) => (
                              <TableRow key={entry.model_name} className={entry.rank === 1 ? "bg-green-50 dark:bg-green-900/20" : ""}>
                                <TableCell>{entry.rank === 1 ? <Trophy className="h-4 w-4 text-yellow-500" /> : entry.rank}</TableCell>
                                <TableCell className="font-medium">{entry.model_name}</TableCell>
                                {Object.values(entry.metrics).map((v, i) => (
                                  <TableCell key={i} className="text-right font-mono">{v.toFixed(4)}</TableCell>
                                ))}
                                <TableCell className="text-right text-muted-foreground">{entry.training_time_seconds.toFixed(1)}s</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </>
                )}

                <div className="flex gap-4 text-xs text-muted-foreground border-t pt-3">
                  <span>Created: {new Date(selectedJob.created_at).toLocaleString()}</span>
                  {selectedJob.completed_at && (
                    <span>Completed: {new Date(selectedJob.completed_at).toLocaleString()}</span>
                  )}
                  {selectedJob.author_username && (
                    <span>By: {selectedJob.author_username}</span>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
