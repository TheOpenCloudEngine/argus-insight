"use client"

import { useCallback, useEffect, useState } from "react"
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Database,
  FlaskConical,
  Loader2,
  Play,
  Rocket,
  Settings2,
  Target,
  Trophy,
  Upload,
} from "lucide-react"
import { AgGridReact } from "ag-grid-react"
import { AllCommunityModule, ModuleRegistry } from "ag-grid-community"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"

ModuleRegistry.registerModules([AllCommunityModule])
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"

import { authFetch } from "@/features/auth/auth-fetch"
import { FilePickerDialog } from "@/features/ml-studio/components/file-picker-dialog"

// ── Types ─────────────────────────────────────────────────

interface ColumnInfo {
  name: string
  dtype: string
  missing: number
  unique: number
  sample_values: string[]
  min_value: string | null
  max_value: string | null
  category_values: string[] | null
}

interface LeaderboardEntry {
  rank: number
  model_name: string
  metrics: Record<string, number>
  training_time_seconds: number
}

interface JobResult {
  leaderboard: LeaderboardEntry[]
  best_model: LeaderboardEntry | null
  feature_importance: Record<string, number>
  metric_key: string
}

// ── Step indicator ────────────────────────────────────────

const STEPS = [
  { id: 1, label: "Data", icon: Database },
  { id: 2, label: "Task", icon: Target },
  { id: 3, label: "Features", icon: Settings2 },
  { id: 4, label: "Train", icon: Play },
  { id: 5, label: "Results", icon: Trophy },
]

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center justify-center gap-1 pb-6">
      {STEPS.map((step, i) => {
        const done = current > step.id
        const active = current === step.id
        const Icon = step.icon
        return (
          <div key={step.id} className="flex items-center">
            <div className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-colors ${
              active ? "bg-primary text-primary-foreground" :
              done ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" :
              "bg-muted text-muted-foreground"
            }`}>
              {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Icon className="h-3.5 w-3.5" />}
              <span>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`mx-1 h-px w-8 ${current > step.id ? "bg-green-500" : "bg-border"}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Main Wizard ───────────────────────────────────────────

export function MLStudioWizard() {
  const [step, setStep] = useState(1)
  const [workspaceId, setWorkspaceId] = useState<number | null>(null)

  // Step 1: Data
  const [bucket, setBucket] = useState("")
  const [filePath, setFilePath] = useState("")
  const [filePickerOpen, setFilePickerOpen] = useState(false)
  const [columns, setColumns] = useState<ColumnInfo[]>([])
  const [sampleRows, setSampleRows] = useState<Record<string, string>[]>([])
  const [rowCount, setRowCount] = useState(0)
  const [previewing, setPreviewing] = useState(false)

  // Step 2: Task
  const [taskType, setTaskType] = useState("classification")
  const [targetColumn, setTargetColumn] = useState("")
  const [metric, setMetric] = useState("auto")

  // Step 3: Features
  const [selectedFeatures, setSelectedFeatures] = useState<Set<string>>(new Set())
  const [algorithm, setAlgorithm] = useState("auto")
  const [timeLimit, setTimeLimit] = useState("300")

  // Step 4: Train
  const [jobId, setJobId] = useState<number | null>(null)
  const [jobStatus, setJobStatus] = useState("")
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState<JobResult | null>(null)
  const [errorMsg, setErrorMsg] = useState("")

  // Load workspace ID
  useEffect(() => {
    const stored = sessionStorage.getItem("argus_last_workspace_id")
    if (stored) {
      setWorkspaceId(Number(stored))
    } else {
      authFetch("/api/v1/workspace/workspaces/my")
        .then((r) => (r.ok ? r.json() : []))
        .then((ws: { id: number }[]) => {
          if (ws.length > 0) {
            setWorkspaceId(ws[0]!.id)
            sessionStorage.setItem("argus_last_workspace_id", String(ws[0]!.id))
          }
        })
        .catch(() => {})
    }
  }, [])

  // Preview data
  const handlePreview = useCallback(async () => {
    if (!workspaceId || !bucket || !filePath) return
    setPreviewing(true)
    try {
      const res = await authFetch("/api/v1/ml-studio/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          source_type: "minio",
          path: filePath,
          bucket,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setColumns(data.columns)
        setSampleRows(data.sample_rows)
        setRowCount(data.row_count)
        // Auto-select all features
        setSelectedFeatures(new Set(data.columns.map((c: ColumnInfo) => c.name)))
      }
    } catch { /* ignore */ }
    finally { setPreviewing(false) }
  }, [workspaceId, bucket, filePath])

  // Start training
  const handleTrain = useCallback(async () => {
    if (!workspaceId || !targetColumn) return
    setJobStatus("pending")
    setProgress(0)
    setResults(null)
    setErrorMsg("")
    setStep(4)

    try {
      const features = Array.from(selectedFeatures).filter((f) => f !== targetColumn)
      const res = await authFetch("/api/v1/ml-studio/train", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          name: `${taskType}-${targetColumn}-${Date.now()}`,
          task_type: taskType,
          target_column: targetColumn,
          metric,
          algorithm,
          data_source: { type: "minio", bucket, path: filePath },
          feature_columns: features,
          exclude_columns: [],
          time_limit_seconds: parseInt(timeLimit),
          test_split: 0.2,
        }),
      })
      if (!res.ok) throw new Error("Failed to start training")
      const job = await res.json()
      setJobId(job.id)
      setJobStatus("running")

      // Poll for status
      const poll = setInterval(async () => {
        try {
          const statusRes = await authFetch(`/api/v1/ml-studio/jobs/${job.id}`)
          if (!statusRes.ok) return
          const j = await statusRes.json()
          setProgress(j.progress)
          setJobStatus(j.status)
          if (j.results) setResults(j.results)
          if (j.error_message) setErrorMsg(j.error_message)
          if (j.status === "completed" || j.status === "failed") {
            clearInterval(poll)
            if (j.status === "completed") setStep(5)
          }
        } catch { /* ignore */ }
      }, 2000)
    } catch (e) {
      setJobStatus("failed")
      setErrorMsg((e as Error).message)
    }
  }, [workspaceId, taskType, targetColumn, metric, algorithm, selectedFeatures, bucket, filePath, timeLimit])

  // Toggle feature selection
  const toggleFeature = (name: string) => {
    setSelectedFeatures((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  // ── Render Steps ────────────────────────────────────────

  return (
    <div className="flex flex-1 flex-col" style={{ minHeight: 0 }}>
      <StepIndicator current={step} />

      {/* Step 1: Data */}
      {step === 1 && (
        <Card className="flex flex-1 flex-col">
          <CardHeader className="shrink-0 py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Database className="h-4 w-4" /> Select Data Source
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col space-y-4 text-sm min-h-0">
            {/* File selector */}
            <div className="space-y-1.5">
              <Label className="text-sm">Data File</Label>
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm" onClick={() => setFilePickerOpen(true)}>
                  <Upload className="mr-1.5 h-4 w-4" /> Select File
                </Button>
                {bucket && filePath ? (
                  <div className="flex items-center gap-2 text-sm">
                    <Badge variant="secondary" className="font-mono text-xs">{bucket}</Badge>
                    <span className="text-muted-foreground">/</span>
                    <span className="font-mono">{filePath}</span>
                    {previewing && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
                  </div>
                ) : (
                  <span className="text-sm text-muted-foreground">Select a data file from MinIO</span>
                )}
              </div>
            </div>

            {/* Supported formats info */}
            {!bucket && (
              <div className="rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground space-y-1">
                <p className="font-medium text-foreground">Supported File Formats</p>
                <ul className="list-disc pl-5 space-y-0.5">
                  <li><strong>CSV</strong> — Comma Separated Values (auto-detected delimiter: <code className="bg-muted px-1 rounded">,</code> <code className="bg-muted px-1 rounded">;</code> <code className="bg-muted px-1 rounded">|</code> <code className="bg-muted px-1 rounded">\t</code>)</li>
                  <li><strong>TSV</strong> — Tab Separated Values</li>
                  <li><strong>Parquet</strong> — Apache Parquet columnar format</li>
                  <li><strong>Excel</strong> — .xlsx, .xls (first sheet only)</li>
                </ul>
                <p className="text-xs pt-1">CSV/TSV: first row must be column headers, UTF-8 encoding recommended.</p>
              </div>
            )}

            <FilePickerDialog
              open={filePickerOpen}
              onOpenChange={setFilePickerOpen}
              onSelect={(b, p) => {
                setBucket(b)
                setFilePath(p)
                setColumns([])
                setSampleRows([])
                setTimeout(() => {
                  setPreviewing(true)
                  authFetch("/api/v1/ml-studio/preview", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ workspace_id: workspaceId, source_type: "minio", path: p, bucket: b }),
                  })
                    .then((r) => (r.ok ? r.json() : null))
                    .then((data) => {
                      if (data) {
                        setColumns(data.columns)
                        setSampleRows(data.sample_rows)
                        setRowCount(data.row_count)
                        setSelectedFeatures(new Set(data.columns.map((c: ColumnInfo) => c.name)))
                      }
                    })
                    .catch(() => {})
                    .finally(() => setPreviewing(false))
                }, 100)
              }}
            />

            {/* Column Profile — AG-Grid */}
            {columns.length > 0 && (
              <div className="flex flex-1 flex-col min-h-0">
                <div className="flex items-center justify-between pb-1">
                  <Label className="text-sm">Column Profile</Label>
                  <span className="text-xs text-muted-foreground">{rowCount.toLocaleString()} rows · {columns.length} columns</span>
                </div>
                <div className="ag-theme-alpine flex-1" style={{ width: "100%" }}>
                  <style>{`.ag-theme-alpine { --ag-font-family: inherit; --ag-font-size: var(--text-sm); }`}</style>
                  <AgGridReact
                    rowData={columns.map((c) => ({
                      name: c.name,
                      dtype: c.dtype,
                      missing: c.missing,
                      unique: c.unique,
                      min: c.min_value ?? "—",
                      max: c.max_value ?? "—",
                      sample: c.sample_values.join(", "),
                    }))}
                    columnDefs={[
                      { headerName: "Column", field: "name", minWidth: 120, flex: 1, cellStyle: { fontFamily: "D2Coding, monospace" } },
                      {
                        headerName: "Type", field: "dtype", width: 100,
                        editable: true,
                        cellEditor: "agSelectCellEditor",
                        cellEditorParams: {
                          values: ["integer", "float", "boolean", "datetime", "category", "string", "exclude"],
                        },
                        cellStyle: (params: any) => {
                          const v = params.value
                          if (v === "exclude") return { color: "#dc2626", fontStyle: "italic" }
                          return {}
                        },
                      },
                      { headerName: "Missing", field: "missing", width: 70, cellStyle: { textAlign: "right" } },
                      { headerName: "Unique", field: "unique", width: 70, cellStyle: { textAlign: "right" } },
                      { headerName: "Min", field: "min", width: 130, cellStyle: { fontFamily: "D2Coding, monospace" } },
                      { headerName: "Max", field: "max", width: 130, cellStyle: { fontFamily: "D2Coding, monospace" } },
                      { headerName: "Sample", field: "sample", minWidth: 150, flex: 1, cellStyle: { color: "#888" } },
                    ] as any[]}
                    headerHeight={24}
                    rowHeight={28}
                    singleClickEdit={true}
                    onCellValueChanged={(event: any) => {
                      if (event.colDef.field === "dtype" && event.data) {
                        setColumns((prev) =>
                          prev.map((c) =>
                            c.name === event.data.name ? { ...c, dtype: event.newValue } : c,
                          ),
                        )
                      }
                    }}
                  />
                </div>
              </div>
            )}

            <div className="flex justify-end">
              <Button onClick={() => setStep(2)} disabled={columns.length === 0}>
                Next <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Task */}
      {step === 2 && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Target className="h-4 w-4" /> Define Task
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="space-y-2">
              <Label className="text-sm">Task Type</Label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { value: "classification", label: "Classification", desc: "Predict categories" },
                  { value: "regression", label: "Regression", desc: "Predict numbers" },
                  { value: "timeseries", label: "Time Series", desc: "Forecast future" },
                ].map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setTaskType(t.value)}
                    className={`rounded-lg border p-3 text-left transition-colors ${
                      taskType === t.value ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                    }`}
                  >
                    <p className="font-medium text-sm">{t.label}</p>
                    <p className="text-xs text-muted-foreground">{t.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-sm">Target Column</Label>
                <Select value={targetColumn} onValueChange={setTargetColumn}>
                  <SelectTrigger className="text-sm"><SelectValue placeholder="Select target" /></SelectTrigger>
                  <SelectContent>
                    {columns.map((c) => (
                      <SelectItem key={c.name} value={c.name} className="text-sm">{c.name} ({c.dtype})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Evaluation Metric</Label>
                <Select value={metric} onValueChange={setMetric}>
                  <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto" className="text-sm">Auto (recommended)</SelectItem>
                    {taskType === "classification" ? (
                      <>
                        <SelectItem value="f1" className="text-sm">F1 Score</SelectItem>
                        <SelectItem value="accuracy" className="text-sm">Accuracy</SelectItem>
                        <SelectItem value="auc" className="text-sm">AUC</SelectItem>
                      </>
                    ) : (
                      <>
                        <SelectItem value="rmse" className="text-sm">RMSE</SelectItem>
                        <SelectItem value="mae" className="text-sm">MAE</SelectItem>
                        <SelectItem value="r2" className="text-sm">R²</SelectItem>
                      </>
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>
                <ArrowLeft className="mr-1 h-4 w-4" /> Back
              </Button>
              <Button onClick={() => setStep(3)} disabled={!targetColumn}>
                Next <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Features */}
      {step === 3 && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Settings2 className="h-4 w-4" /> Select Features & Algorithm
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="max-h-[300px] overflow-auto rounded-lg border text-sm">
              <Table>
                <TableHeader className="sticky top-0 z-10 bg-background">
                  <TableRow>
                    <TableHead className="w-10"></TableHead>
                    <TableHead className="text-sm">Column</TableHead>
                    <TableHead className="text-sm">Type</TableHead>
                    <TableHead className="text-sm">Missing</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {columns.filter((c) => c.name !== targetColumn).map((col) => (
                    <TableRow key={col.name}>
                      <TableCell>
                        <Checkbox
                          checked={selectedFeatures.has(col.name)}
                          onCheckedChange={() => toggleFeature(col.name)}
                        />
                      </TableCell>
                      <TableCell className="font-mono">{col.name}</TableCell>
                      <TableCell>{col.dtype}</TableCell>
                      <TableCell>{col.missing}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-sm">Algorithm</Label>
                <Select value={algorithm} onValueChange={setAlgorithm}>
                  <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto" className="text-sm">Auto (try all)</SelectItem>
                    <SelectItem value="xgboost" className="text-sm">XGBoost</SelectItem>
                    <SelectItem value="lightgbm" className="text-sm">LightGBM</SelectItem>
                    <SelectItem value="random_forest" className="text-sm">Random Forest</SelectItem>
                    <SelectItem value="linear" className="text-sm">Linear / Logistic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Time Limit</Label>
                <Select value={timeLimit} onValueChange={setTimeLimit}>
                  <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="60" className="text-sm">1 minute</SelectItem>
                    <SelectItem value="300" className="text-sm">5 minutes</SelectItem>
                    <SelectItem value="600" className="text-sm">10 minutes</SelectItem>
                    <SelectItem value="1800" className="text-sm">30 minutes</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}>
                <ArrowLeft className="mr-1 h-4 w-4" /> Back
              </Button>
              <Button onClick={handleTrain} disabled={selectedFeatures.size === 0}>
                <FlaskConical className="mr-1.5 h-4 w-4" /> Start Training
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Training */}
      {step === 4 && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Play className="h-4 w-4" /> Training
              {jobStatus === "running" && <Badge className="bg-blue-100 text-blue-800 text-[10px]">Running</Badge>}
              {jobStatus === "completed" && <Badge className="bg-green-100 text-green-800 text-[10px]">Completed</Badge>}
              {jobStatus === "failed" && <Badge className="bg-red-100 text-red-800 text-[10px]">Failed</Badge>}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {/* Progress bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Progress</span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-muted">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${jobStatus === "failed" ? "bg-red-500" : "bg-primary"}`}
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {errorMsg && (
              <p className="text-sm text-red-500">{errorMsg}</p>
            )}

            {jobStatus === "running" && !results && (
              <div className="flex flex-col items-center justify-center py-8 gap-3">
                <div className="flex items-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  <span className="ml-3 text-muted-foreground">Training models...</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Training runs in the background. You can leave this page and check results in the <strong>Experiments</strong> tab.
                </p>
              </div>
            )}

            {results && results.leaderboard.length > 0 && (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10 text-sm">#</TableHead>
                      <TableHead className="text-sm">Model</TableHead>
                      {Object.keys(results.leaderboard[0]!.metrics).map((k) => (
                        <TableHead key={k} className="text-right text-sm">
                          {k === results.metric_key ? <strong>{k}</strong> : k}
                        </TableHead>
                      ))}
                      <TableHead className="text-right text-sm">Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {results.leaderboard.map((entry) => (
                      <TableRow key={entry.model_name} className={entry.rank === 1 ? "bg-green-50 dark:bg-green-900/20" : ""}>
                        <TableCell className="text-sm">
                          {entry.rank === 1 ? <Trophy className="h-4 w-4 text-yellow-500" /> : entry.rank}
                        </TableCell>
                        <TableCell className="font-medium text-sm">{entry.model_name}</TableCell>
                        {Object.entries(entry.metrics).map(([k, v]) => (
                          <TableCell key={k} className="text-right font-mono text-sm">
                            {v.toFixed(4)}
                          </TableCell>
                        ))}
                        <TableCell className="text-right text-sm text-muted-foreground">
                          {entry.training_time_seconds.toFixed(1)}s
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Step 5: Results & Deploy */}
      {step === 5 && results && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Trophy className="h-4 w-4" /> Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid gap-4 lg:grid-cols-2">
              {/* Best Model */}
              {results.best_model && (
                <Card>
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Trophy className="h-5 w-5 text-yellow-500" />
                      <span className="font-semibold">{results.best_model.model_name}</span>
                      <Badge className="bg-green-100 text-green-800 text-[10px]">Best</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(results.best_model.metrics).map(([k, v]) => (
                        <div key={k} className="flex justify-between">
                          <span className="text-muted-foreground">{k}</span>
                          <span className="font-mono font-medium">{v.toFixed(4)}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Feature Importance */}
              {results.feature_importance && (
                <Card>
                  <CardContent className="pt-4">
                    <p className="font-semibold mb-3 flex items-center gap-2">
                      <BarChart3 className="h-4 w-4" /> Feature Importance
                    </p>
                    <div className="space-y-2">
                      {Object.entries(results.feature_importance)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 8)
                        .map(([name, value]) => (
                          <div key={name} className="flex items-center gap-2">
                            <span className="w-28 truncate text-xs">{name}</span>
                            <div className="flex-1 h-3 rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-primary"
                                style={{ width: `${Math.min(value * 100 * 3, 100)}%` }}
                              />
                            </div>
                            <span className="text-xs font-mono w-12 text-right">{(value * 100).toFixed(1)}%</span>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Leaderboard */}
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10 text-sm">#</TableHead>
                    <TableHead className="text-sm">Model</TableHead>
                    {results.leaderboard.length > 0 && Object.keys(results.leaderboard[0]!.metrics).map((k) => (
                      <TableHead key={k} className="text-right text-sm">{k}</TableHead>
                    ))}
                    <TableHead className="text-right text-sm">Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.leaderboard.map((entry) => (
                    <TableRow key={entry.model_name} className={entry.rank === 1 ? "bg-green-50 dark:bg-green-900/20" : ""}>
                      <TableCell className="text-sm">{entry.rank === 1 ? <Trophy className="h-4 w-4 text-yellow-500" /> : entry.rank}</TableCell>
                      <TableCell className="font-medium text-sm">{entry.model_name}</TableCell>
                      {Object.entries(entry.metrics).map(([k, v]) => (
                        <TableCell key={k} className="text-right font-mono text-sm">{v.toFixed(4)}</TableCell>
                      ))}
                      <TableCell className="text-right text-sm text-muted-foreground">{entry.training_time_seconds.toFixed(1)}s</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Actions */}
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => { setStep(1); setResults(null); setJobId(null) }}>
                <FlaskConical className="mr-1.5 h-4 w-4" /> New Experiment
              </Button>
              <Button>
                <Rocket className="mr-1.5 h-4 w-4" /> Deploy Best Model
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
