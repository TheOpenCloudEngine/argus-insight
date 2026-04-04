"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  BarChart3,
  CheckCircle2,
  Clock,
  Code,
  FileText,
  FlaskConical,
  Loader2,
  ScrollText,
  Trophy,
  Workflow,
  XCircle,
} from "lucide-react"
import { AgGridReact } from "ag-grid-react"
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type PaginationNumberFormatterParams,
} from "ag-grid-community"
import Editor from "@monaco-editor/react"
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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@workspace/ui/components/tabs"

import { authFetch } from "@/features/auth/auth-fetch"

ModuleRegistry.registerModules([AllCommunityModule])

// ── Types ─────────────────────────────────────────────────

interface TrainJob {
  id: number
  name: string
  source: string  // wizard | modeler
  status: string
  task_type: string
  target_column: string
  metric: string
  algorithm: string
  progress: number
  results: {
    leaderboard?: { rank: number; model_name: string; metrics: Record<string, number>; training_time_seconds: number }[]
    best_model?: { model_name: string; metrics: Record<string, number> } | null
    feature_importance?: Record<string, number>
    classification_report?: { class: string; precision: number; recall: number; f1_score: number; support: number }[]
    metric_key?: string
    status?: string
    message?: string
  } | null
  error_message: string | null
  pipeline_id: number | null
  generated_code: string | null
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

function formatDuration(startStr: string, endStr: string | null, status: string): string {
  const start = new Date(startStr).getTime()
  const end = endStr
    ? new Date(endStr).getTime()
    : (status === "running" || status === "pending" ? Date.now() : start)
  const sec = Math.floor((end - start) / 1000)
  if (sec < 60) return `${sec}s`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`
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
  pipeline: "Pipeline",
}

// ── Wizard Detail ─────────────────────────────────────────

function WizardJobDetail({ job }: { job: TrainJob }) {
  return (
    <div className="space-y-4 text-sm">
      {/* Info */}
      <div className="grid grid-cols-4 gap-3">
        <div>
          <span className="text-xs text-muted-foreground">Task</span>
          <p>{TASK_LABELS[job.task_type] || job.task_type}</p>
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Target</span>
          <p className="font-mono">{job.target_column}</p>
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Metric</span>
          <p>{job.metric}</p>
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Algorithm</span>
          <p>{job.algorithm}</p>
        </div>
      </div>

      <JobProgress job={job} />
      <JobError job={job} />

      {/* Results */}
      {job.results && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            {job.results.best_model && (
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Trophy className="h-5 w-5 text-yellow-500" />
                    <span className="font-semibold">{job.results.best_model.model_name}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(job.results.best_model.metrics).map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-muted-foreground">{k}</span>
                        <span className="font-mono font-medium">{v.toFixed(4)}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
            <FeatureImportanceCard importance={job.results.feature_importance} />
          </div>
          <LeaderboardTable leaderboard={job.results.leaderboard} />
        </>
      )}

      <JobFooter job={job} />
    </div>
  )
}

// ── Modeler Detail (3 tabs) ───────────────────────────────

function ModelerJobDetail({ job }: { job: TrainJob }) {
  const [activeTab, setActiveTab] = useState("results")
  const [logs, setLogs] = useState<string>("")
  const [logsLoading, setLogsLoading] = useState(false)

  const fetchLogs = async () => {
    setLogsLoading(true)
    try {
      const wsId = sessionStorage.getItem("argus_last_workspace_id")
      if (!wsId) return
      const res = await authFetch(
        `/api/v1/ml-studio/jobs/${job.id}/logs?workspace_id=${wsId}`,
      )
      if (res.ok) {
        const data = await res.json()
        setLogs(data.logs || "No logs available")
      } else {
        setLogs("Failed to fetch logs")
      }
    } catch {
      setLogs("Failed to fetch logs")
    } finally {
      setLogsLoading(false)
    }
  }

  // Auto-fetch logs when switching to logs tab
  useEffect(() => {
    if (activeTab === "logs" && !logs) {
      fetchLogs()
    }
  }, [activeTab])

  // Auto-refresh logs while job is running and logs tab is active
  useEffect(() => {
    if (activeTab !== "logs") return
    const isActive = job.status === "running" || job.status === "pending"
    if (!isActive) return
    const interval = setInterval(fetchLogs, 3000)
    return () => clearInterval(interval)
  }, [activeTab, job.status])

  return (
    <div className="space-y-3 text-sm">
      <JobProgress job={job} />
      <JobError job={job} />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="h-8">
          <TabsTrigger value="results" className="text-sm h-7 gap-1.5">
            <BarChart3 className="h-3.5 w-3.5" /> Results
          </TabsTrigger>
          <TabsTrigger value="code" className="text-sm h-7 gap-1.5">
            <Code className="h-3.5 w-3.5" /> Code
          </TabsTrigger>
          <TabsTrigger value="logs" className="text-sm h-7 gap-1.5">
            <ScrollText className="h-3.5 w-3.5" /> Logs
          </TabsTrigger>
        </TabsList>

        {/* Fixed-height content area — consistent across all tabs */}
        <div style={{ height: "45vh", marginTop: 12 }}>
          {/* Results tab */}
          <TabsContent value="results" className="mt-0 h-full overflow-y-auto space-y-4">
            {job.results ? (
              <>
                {job.results.message && (
                  <p className="text-sm text-muted-foreground">{job.results.message}</p>
                )}
                {job.results.best_model && (
                  <div className="grid gap-4 lg:grid-cols-2">
                    <Card>
                      <CardContent className="pt-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Trophy className="h-5 w-5 text-yellow-500" />
                          <span className="font-semibold">{job.results.best_model.model_name}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(job.results.best_model.metrics).map(([k, v]) => (
                            <div key={k} className="flex justify-between">
                              <span className="text-muted-foreground">{k}</span>
                              <span className="font-mono font-medium">{v.toFixed(4)}</span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                    <FeatureImportanceCard importance={job.results.feature_importance} />
                  </div>
                )}
                {/* Per-class Performance */}
                {job.results.classification_report && job.results.classification_report.length > 0 && (() => {
                  const classes = job.results.classification_report!.filter((r) => !r.class.includes("avg") && r.class !== "accuracy")
                  const averages = job.results.classification_report!.filter((r) => r.class.includes("avg"))
                  if (classes.length === 0) return null
                  return (
                    <Card>
                      <CardContent className="pt-4">
                        <p className="font-semibold mb-3 flex items-center gap-2">
                          <BarChart3 className="h-4 w-4" /> Per-class Performance
                        </p>
                        <div className="space-y-3">
                          {classes.map((row) => (
                            <div key={row.class}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium">{row.class}</span>
                                <span className="text-xs text-muted-foreground">{row.support} samples</span>
                              </div>
                              <div className="grid grid-cols-3 gap-2">
                                <div>
                                  <div className="flex justify-between text-xs text-muted-foreground mb-0.5">
                                    <span>Precision</span>
                                    <span className="font-mono">{(row.precision * 100).toFixed(1)}%</span>
                                  </div>
                                  <div className="h-2 rounded-full bg-muted">
                                    <div className="h-full rounded-full bg-blue-500" style={{ width: `${row.precision * 100}%` }} />
                                  </div>
                                </div>
                                <div>
                                  <div className="flex justify-between text-xs text-muted-foreground mb-0.5">
                                    <span>Recall</span>
                                    <span className="font-mono">{(row.recall * 100).toFixed(1)}%</span>
                                  </div>
                                  <div className="h-2 rounded-full bg-muted">
                                    <div className="h-full rounded-full bg-emerald-500" style={{ width: `${row.recall * 100}%` }} />
                                  </div>
                                </div>
                                <div>
                                  <div className="flex justify-between text-xs text-muted-foreground mb-0.5">
                                    <span>F1</span>
                                    <span className="font-mono">{(row.f1_score * 100).toFixed(1)}%</span>
                                  </div>
                                  <div className="h-2 rounded-full bg-muted">
                                    <div className="h-full rounded-full bg-violet-500" style={{ width: `${row.f1_score * 100}%` }} />
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                        {averages.length > 0 && (
                          <div className="mt-3 pt-3 border-t flex gap-6 text-xs text-muted-foreground">
                            {averages.map((avg) => (
                              <span key={avg.class} className="font-mono">
                                {avg.class}: F1={<span className="font-semibold text-foreground">{(avg.f1_score * 100).toFixed(1)}%</span>}
                              </span>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )
                })()}
                <LeaderboardTable leaderboard={job.results.leaderboard} />
                {!job.results.best_model && !job.results.leaderboard?.length && !job.results.classification_report?.length && (
                  <div className="text-center py-8 text-muted-foreground">
                    <CheckCircle2 className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Pipeline executed successfully</p>
                  </div>
                )}
              </>
            ) : job.status === "completed" ? (
              <p className="text-sm text-muted-foreground py-4">No structured results</p>
            ) : (
              <p className="text-sm text-muted-foreground py-4">Results will appear after execution completes</p>
            )}
          </TabsContent>

          {/* Code tab */}
          <TabsContent value="code" className="mt-0 h-full">
            {job.generated_code ? (
              <div className="rounded border overflow-hidden h-full">
                <Editor
                  height="100%"
                  language="python"
                  value={job.generated_code}
                  options={{
                    readOnly: true,
                    minimap: { enabled: false },
                    fontFamily: "'D2Coding', 'D2 Coding', monospace",
                    fontSize: 13,
                    lineNumbers: "on",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    domReadOnly: true,
                    padding: { top: 8 },
                  }}
                  theme="vs-dark"
                />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-4">No code available</p>
            )}
          </TabsContent>

          {/* Logs tab */}
          <TabsContent value="logs" className="mt-0 h-full flex flex-col">
            <div className="flex justify-end mb-2">
              <button
                type="button"
                onClick={fetchLogs}
                disabled={logsLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded border border-input bg-background hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
              >
                <Loader2 className={`h-3 w-3 ${logsLoading ? "animate-spin" : "hidden"}`} />
                <ScrollText className={`h-3 w-3 ${logsLoading ? "hidden" : ""}`} />
                Refresh
              </button>
            </div>
            {logsLoading && !logs ? (
              <div className="flex items-center justify-center flex-1">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : logs ? (
              <div className="rounded border overflow-hidden flex-1">
                <Editor
                  height="100%"
                  language="plaintext"
                  value={logs}
                  options={{
                    readOnly: true,
                    minimap: { enabled: false },
                    fontFamily: "'D2Coding', 'D2 Coding', monospace",
                    fontSize: 12,
                    lineNumbers: "off",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    domReadOnly: true,
                    wordWrap: "on",
                    padding: { top: 8 },
                  }}
                  theme="vs-dark"
                />
              </div>
            ) : (
              <div className="flex items-center justify-center flex-1 text-muted-foreground">
                <p className="text-sm">Loading logs...</p>
              </div>
            )}
          </TabsContent>
        </div>
      </Tabs>

      <JobFooter job={job} />
    </div>
  )
}

// ── Shared sub-components ────────────────────────────────

function JobProgress({ job }: { job: TrainJob }) {
  if (job.status !== "running" && job.status !== "pending") return null
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Progress</span>
        <span>{job.progress}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${job.progress}%` }}
        />
      </div>
    </div>
  )
}

function JobError({ job }: { job: TrainJob }) {
  if (!job.error_message) return null
  return <p className="text-sm text-red-500 whitespace-pre-wrap">{job.error_message}</p>
}

function JobFooter({ job }: { job: TrainJob }) {
  return (
    <div className="flex gap-4 text-xs text-muted-foreground border-t pt-3">
      <span>Created: {new Date(job.created_at).toLocaleString()}</span>
      {job.completed_at && <span>Completed: {new Date(job.completed_at).toLocaleString()}</span>}
      {job.author_username && <span>By: {job.author_username}</span>}
      <span>Duration: {formatDuration(job.created_at, job.completed_at, job.status)}</span>
    </div>
  )
}

function FeatureImportanceCard({ importance }: { importance?: Record<string, number> }) {
  if (!importance || Object.keys(importance).length === 0) return null
  return (
    <Card>
      <CardContent className="pt-4">
        <p className="font-semibold mb-3 flex items-center gap-2">
          <BarChart3 className="h-4 w-4" /> Feature Importance
        </p>
        <div className="space-y-2">
          {Object.entries(importance)
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
  )
}

function LeaderboardTable({ leaderboard }: { leaderboard?: { rank: number; model_name: string; metrics: Record<string, number>; training_time_seconds: number }[] }) {
  if (!leaderboard || leaderboard.length === 0) return null
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10 text-sm">#</TableHead>
            <TableHead className="text-sm">Model</TableHead>
            {Object.keys(leaderboard[0]!.metrics).map((k) => (
              <TableHead key={k} className="text-right text-sm">{k}</TableHead>
            ))}
            <TableHead className="text-right text-sm">Time</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {leaderboard.map((entry) => (
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
  )
}

// ── Main Component ────────────────────────────────────────

export function MLStudioExperiments() {
  const [jobs, setJobs] = useState<TrainJob[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedJob, setSelectedJob] = useState<TrainJob | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const selectedJobRef = useRef(selectedJob)
  selectedJobRef.current = selectedJob

  useEffect(() => {
    async function load() {
      const wsId = sessionStorage.getItem("argus_last_workspace_id")
      if (!wsId) { setLoading(false); return }
      try {
        const res = await authFetch(
          `/api/v1/ml-studio/jobs?workspace_id=${wsId}&page=1&page_size=50`,
        )
        if (res.ok) {
          const data = await res.json()
          const newJobs: TrainJob[] = data.jobs ?? []
          setJobs(newJobs)
          // Sync selectedJob with latest data so progress/results update in dialog
          const cur = selectedJobRef.current
          if (cur) {
            const updated = newJobs.find((j) => j.id === cur.id)
            if (updated) setSelectedJob(updated)
          }
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
        headerName: "Type",
        width: 70,
        valueGetter: (params: any) => (params.data?.source || "wizard") === "modeler" ? "M" : "W",
        cellStyle: (params: any) => {
          const isModeler = (params.data?.source || "wizard") === "modeler"
          return {
            fontWeight: 600,
            color: isModeler ? "#8b5cf6" : "#3b82f6",
            textAlign: "center",
          }
        },
      },
      {
        headerName: "Experiment",
        field: "name",
        minWidth: 220,
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
        valueGetter: (params: any) => params.data?.target_column || "—",
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
          return formatDuration(params.data.created_at, params.data.completed_at, params.data.status)
        },
      },
      {
        headerName: "",
        width: 80,
        sortable: false,
        filter: false,
        cellRenderer: (params: any) => {
          if (!params.data) return ""
          const isActive = params.data.status === "running" || params.data.status === "pending"
          if (!isActive) return ""
          return `<button style="
            display:inline-flex;align-items:center;gap:4px;
            padding:2px 10px;border-radius:4px;font-size:12px;font-weight:600;
            background:#fef2f2;color:#dc2626;border:1px solid #fca5a5;
            cursor:pointer;line-height:20px;
          "><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>Kill</button>`
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
        <p className="text-xs mt-1">Start from the Wizard or Modeler tab</p>
      </div>
    )
  }

  const isModeler = (selectedJob?.source || "wizard") === "modeler"

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
            if (event.colDef?.headerName === "" && (event.data.status === "running" || event.data.status === "pending")) {
              if (confirm(`Cancel job "${event.data.name}"?`)) {
                handleKill(event.data.id)
              }
              return
            }
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

      {/* Detail Dialog — switches between Wizard and Modeler */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-[70vw]">
          {selectedJob && (
            <>
              <DialogHeader>
                <DialogTitle className="text-sm flex items-center gap-2">
                  {isModeler ? (
                    <Workflow className="h-4 w-4 text-violet-500" />
                  ) : (
                    <FlaskConical className="h-4 w-4" />
                  )}
                  {selectedJob.name}
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${isModeler ? "border-violet-400 text-violet-600" : "border-blue-400 text-blue-600"}`}
                  >
                    {isModeler ? "Modeler" : "Wizard"}
                  </Badge>
                  <Badge className={`text-[10px] ${(STATUS_CONFIG[selectedJob.status] || STATUS_CONFIG.pending!).color}`}>
                    {(STATUS_CONFIG[selectedJob.status] || STATUS_CONFIG.pending!).label}
                  </Badge>
                </DialogTitle>
              </DialogHeader>

              {isModeler ? (
                <ModelerJobDetail job={selectedJob} />
              ) : (
                <WizardJobDetail job={selectedJob} />
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
