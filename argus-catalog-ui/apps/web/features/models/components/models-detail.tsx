"use client"

import { useEffect, useState } from "react"
import dynamic from "next/dynamic"
import {
  ArrowLeft, User, Clock, GitBranch, Loader2, Activity,
} from "lucide-react"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"

import { CommentSection } from "@/components/comments"
import {
  fetchModelDetail,
  fetchModelVersions,
  fetchModelDownloadStats,
  type ModelDetail,
  type ModelVersionItem,
  type ModelDownloadStats,
} from "../api"

const MonacoEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.default), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[200px]">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  ),
})

function formatSize(bytes: number | null): string {
  if (!bytes) return "-"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  })
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  })
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  if (days === 0) return "today"
  if (days === 1) return "1d ago"
  if (days < 30) return `${days}d ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`
  return `${Math.floor(days / 365)}y ago`
}

function StatusBadge({ status }: { status: string | null }) {
  let bg = "bg-orange-500"
  let label = "N/A"
  if (status === "READY") { bg = "bg-blue-500"; label = "READY" }
  else if (status === "PENDING_REGISTRATION") { bg = "bg-zinc-400"; label = "PENDING" }
  else if (status === "FAILED_REGISTRATION") { bg = "bg-red-500"; label = "FAILED" }
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-semibold text-white ${bg}`}>
      {label}
    </span>
  )
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-start gap-3 py-1.5 border-b last:border-b-0">
      <span className="text-sm text-muted-foreground w-36 shrink-0">{label}</span>
      <span className="text-sm break-all">{value || "-"}</span>
    </div>
  )
}

// ─── Overview Tab ───

function OverviewTab({ detail }: { detail: ModelDetail }) {
  const c = detail.catalog
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-sm font-medium">Model Info</CardTitle></CardHeader>
          <CardContent>
            <InfoRow label="Name" value={detail.name} />
            <InfoRow label="URN" value={detail.urn} />
            <InfoRow label="Owner" value={detail.owner} />
            <InfoRow label="Storage Type" value={detail.storage_type} />
            <InfoRow label="Created" value={formatDateTime(detail.created_at)} />
            <InfoRow label="Updated" value={formatDateTime(detail.updated_at)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-sm font-medium">Latest Version (v{detail.max_version_number})</CardTitle></CardHeader>
          <CardContent>
            {c ? (
              <>
                <InfoRow label="Status" value={detail.latest_version_status} />
                <InfoRow label="predict_fn" value={c.predict_fn} />
                <InfoRow label="Python" value={c.python_version} />
                <InfoRow label="sklearn" value={c.sklearn_version} />
                <InfoRow label="MLflow" value={c.mlflow_version} />
                <InfoRow label="Serialization" value={c.serialization_format} />
                <InfoRow label="Model Size" value={formatSize(c.model_size_bytes)} />
                <InfoRow label="Model ID" value={c.mlflow_model_id} />
                <InfoRow label="Created (UTC)" value={c.utc_time_created} />
                <InfoRow
                  label="Created (Local)"
                  value={c.utc_time_created
                    ? new Date(c.utc_time_created.replace(" ", "T") + "Z").toLocaleString()
                    : null}
                />
              </>
            ) : (
              <p className="text-sm text-muted-foreground py-4">No metadata available</p>
            )}
          </CardContent>
        </Card>
      </div>

      {c && (c.requirements || c.conda) && (
        <div className="grid gap-4 lg:grid-cols-2">
          {c.requirements && (
            <Card>
              <CardHeader><CardTitle className="text-sm font-medium">Requirements</CardTitle></CardHeader>
              <CardContent>
                <div className="h-[200px] overflow-hidden rounded">
                  <MonacoEditor
                    height="100%"
                    language="plaintext"
                    value={c.requirements}
                    theme="light"
                    options={{ readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 12, lineNumbers: "on", domReadOnly: true, renderLineHighlight: "none", overviewRulerBorder: false, hideCursorInOverviewRuler: true }}
                  />
                </div>
              </CardContent>
            </Card>
          )}
          {c.conda && (
            <Card>
              <CardHeader><CardTitle className="text-sm font-medium">Conda</CardTitle></CardHeader>
              <CardContent>
                <div className="h-[200px] overflow-hidden rounded">
                  <MonacoEditor
                    height="100%"
                    language="yaml"
                    value={c.conda}
                    theme="light"
                    options={{ readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 12, lineNumbers: "on", domReadOnly: true, renderLineHighlight: "none", overviewRulerBorder: false, hideCursorInOverviewRuler: true }}
                  />
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Usage Tab ───

function UsageTab({ detail }: { detail: ModelDetail }) {
  const name = detail.name
  const ver = detail.max_version_number
  const code = `import mlflow
import pandas as pd

# ─── Configuration ───
# Set the Argus Catalog Server as the MLflow Model Registry
mlflow.set_registry_uri("uc:http://<argus-catalog-server>:<argus-catalog-server-port>")


# ─── 1. Load Model & Predict ───

# Load a specific version
model = mlflow.pyfunc.load_model("models:/${name}/${ver}")

# Prepare your input data
X_new = pd.DataFrame(
    # TODO: Replace with your actual input data
    [[...], [...]],
    columns=["feature_1", "feature_2", ...],
)

# Run inference
predictions = model.predict(X_new)
print("Predictions:", predictions)


# ─── 2. Load Latest Version ───

latest_model = mlflow.pyfunc.load_model("models:/${name}/latest")
print("Latest predictions:", latest_model.predict(X_new))


# ─── 3. Register a New Version ───

# Train your model
# model = YourModel()
# model.fit(X_train, y_train)

# Log and register (creates a new version automatically)
# mlflow.sklearn.log_model(
#     model,
#     "model",
#     registered_model_name="${name}",
# )
`

  return (
    <div className="h-[600px] overflow-hidden rounded">
      <MonacoEditor
        height="100%"
        language="python"
        value={code}
        theme="light"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          fontFamily: "D2Coding, monospace",
          lineNumbers: "on",
          domReadOnly: true,
          renderLineHighlight: "none",
          overviewRulerBorder: false,
          hideCursorInOverviewRuler: true,
        }}
      />
    </div>
  )
}

// ─── Versions Tab ───

function VersionsTab({ modelName }: { modelName: string }) {
  const [versions, setVersions] = useState<ModelVersionItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchModelVersions(modelName, 1, 100)
      .then((data) => setVersions(data.items))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [modelName])

  if (loading) return <div className="text-center py-12 text-muted-foreground">Loading versions...</div>

  return (
    <div className="border rounded-md overflow-auto">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 sticky top-0">
          <tr>
            <th className="px-3 py-2 text-left font-medium w-20">Version</th>
            <th className="px-3 py-2 text-center font-medium w-24">Status</th>
            <th className="px-3 py-2 text-center font-medium w-20">Files</th>
            <th className="px-3 py-2 text-center font-medium w-24">Size</th>
            <th className="px-3 py-2 text-center font-medium w-28">Finished</th>
            <th className="px-3 py-2 text-left font-medium">Run ID</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {versions.map((v) => (
            <tr key={v.id} className="hover:bg-muted/30">
              <td className="px-3 py-2">v{v.version}</td>
              <td className="px-3 py-2 text-center"><StatusBadge status={v.status} /></td>
              <td className="px-3 py-2 text-center">{v.artifact_count}</td>
              <td className="px-3 py-2 text-center">{formatSize(v.artifact_size)}</td>
              <td className="px-3 py-2 text-center" title={v.finished_at || ""}>
                {v.finished_at ? timeAgo(v.finished_at) : "-"}
              </td>
              <td className="px-3 py-2 font-mono truncate max-w-[200px]">
                {v.run_id || "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Download Tab ───

function DownloadTab({ modelName }: { modelName: string }) {
  const [stats, setStats] = useState<ModelDownloadStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchModelDownloadStats(modelName)
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [modelName])

  if (loading || !stats) return <div className="text-center py-12 text-muted-foreground">Loading download data...</div>

  const chartData = stats.daily_download.map((d) => ({
    date: d.date.slice(5),
    fullDate: d.date,
    count: d.count,
  }))

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Daily Download (30 days)</CardTitle>
        </CardHeader>
        <CardContent>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" fontSize={10} />
                <YAxis allowDecimals={false} fontSize={11} />
                <Tooltip labelFormatter={(_, p) => p?.[0]?.payload?.fullDate || ""} />
                <Line type="monotone" dataKey="count" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">No download data yet</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Recent Download Log</CardTitle>
        </CardHeader>
        <CardContent>
          {stats.recent_logs.length > 0 ? (
            <div className="border rounded-md overflow-auto max-h-[400px]">
              <table className="w-full text-sm">
                <thead className="bg-muted/60 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium w-44">Time</th>
                    <th className="px-3 py-2 text-center font-medium w-16">Ver</th>
                    <th className="px-3 py-2 text-center font-medium w-24">Type</th>
                    <th className="px-3 py-2 text-left font-medium w-32">Client IP</th>
                    <th className="px-3 py-2 text-left font-medium">User Agent</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {stats.recent_logs.map((log, i) => (
                    <tr key={i} className="hover:bg-muted/30">
                      <td className="px-3 py-1.5">{formatDateTime(log.downloaded_at)}</td>
                      <td className="px-3 py-1.5 text-center">v{log.version}</td>
                      <td className="px-3 py-1.5 text-center">
                        <Badge variant="outline" className="text-sm">{log.download_type}</Badge>
                      </td>
                      <td className="px-3 py-1.5 font-mono">{log.client_ip || "-"}</td>
                      <td className="px-3 py-1.5 truncate max-w-[300px]">{log.user_agent || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">No download logs yet</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Main Detail Component ───

type ModelsDetailProps = {
  modelName: string
  onBack: () => void
}

export function ModelsDetail({ modelName, onBack }: ModelsDetailProps) {
  const [detail, setDetail] = useState<ModelDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchModelDetail(modelName)
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [modelName])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <p className="text-sm text-destructive">{error || "Model not found"}</p>
        <Button variant="outline" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Models
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="h-7 px-2" onClick={onBack}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <h1 className="text-xl font-bold">{detail.name}</h1>
            <StatusBadge status={detail.latest_version_status} />
          </div>
          {detail.description && (
            <p className="text-sm text-muted-foreground ml-9">{detail.description}</p>
          )}
          <div className="flex items-center gap-4 text-sm text-muted-foreground ml-9">
            {detail.owner && (
              <span className="flex items-center gap-1">
                <User className="h-3.5 w-3.5" /> {detail.owner}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" /> {formatDate(detail.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <GitBranch className="h-3.5 w-3.5" /> {detail.max_version_number} version{detail.max_version_number !== 1 ? "s" : ""}
            </span>
            <span className="flex items-center gap-1">
              <Activity className="h-3.5 w-3.5" /> {detail.download_count} download
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList variant="line">
          <TabsTrigger value="overview" className="text-base">Overview</TabsTrigger>
          <TabsTrigger value="usage" className="text-base">Usage</TabsTrigger>
          <TabsTrigger value="versions" className="text-base">Versions</TabsTrigger>
          <TabsTrigger value="download" className="text-base">Download</TabsTrigger>
          <TabsTrigger value="comments" className="text-base">Comments</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="mt-4">
          <OverviewTab detail={detail} />
        </TabsContent>
        <TabsContent value="usage" className="mt-4">
          <UsageTab detail={detail} />
        </TabsContent>
        <TabsContent value="versions" className="mt-4">
          <VersionsTab modelName={detail.name} />
        </TabsContent>
        <TabsContent value="download" className="mt-4">
          <DownloadTab modelName={detail.name} />
        </TabsContent>
        <TabsContent value="comments" className="mt-4">
          <CommentSection entityType="model" entityId={detail.name} currentUser="admin" />
        </TabsContent>
      </Tabs>
    </div>
  )
}
