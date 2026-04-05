"use client"

import { useCallback, useEffect, useRef, useState, Fragment } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Container,
  ExternalLink,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  Server,
  Settings,
  Terminal,
  XCircle,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@workspace/ui/components/sheet"
import { Label } from "@workspace/ui/components/label"
import { Separator } from "@workspace/ui/components/separator"
import { authFetch } from "@/features/auth/auth-fetch"
import { useAuth } from "@/features/auth"
import { Avatar, AvatarFallback } from "@workspace/ui/components/avatar"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { Input } from "@workspace/ui/components/input"
import {
  bulkAddWorkspaceMembers,
  deleteWorkspaceService,
  fetchWorkspace,
  fetchWorkspaceMembers,
  fetchWorkspaceServices,
  fetchWorkspaceAuditLogs,
  removeWorkspaceMember,
} from "@/features/workspaces/api"
import type { AuditLog, WorkspaceMember, WorkspaceResponse, WorkspaceService } from "@/features/workspaces/types"
import { PluginIcon } from "@/features/software-deployment/components/plugin-icon"
import { ServiceLogsPanel } from "@/features/workspaces/components/service-logs-panel"
import { WorkspaceDashboardPanel } from "@/features/workspaces/components/workspace-dashboard"

/* ------------------------------------------------------------------ */
/*  Shared helpers                                                     */
/* ------------------------------------------------------------------ */

interface MyWorkspace {
  id: number
  name: string
  display_name: string
  status: string
}

function statusBadge(status: string) {
  switch (status) {
    case "active":
    case "running":
      return (
        <Badge className="bg-green-100 text-green-800 hover:bg-green-100 dark:bg-green-900 dark:text-green-200">
          <CheckCircle2 className="mr-1 h-3 w-3" />
          {status === "active" ? "Active" : "Running"}
        </Badge>
      )
    case "provisioning":
      return (
        <Badge className="animate-pulse bg-blue-100 text-blue-800 hover:bg-blue-100 dark:bg-blue-900 dark:text-blue-200">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          Provisioning
        </Badge>
      )
    case "failed":
      return (
        <Badge className="bg-red-100 text-red-800 hover:bg-red-100 dark:bg-red-900 dark:text-red-200">
          <XCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      )
    default:
      return (
        <Badge variant="secondary">
          <Clock className="mr-1 h-3 w-3" />
          {status}
        </Badge>
      )
  }
}

function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      // Fallback for non-HTTPS environments (e.g., http://10.0.1.50)
      const textarea = document.createElement("textarea")
      textarea.value = value
      textarea.style.position = "fixed"
      textarea.style.opacity = "0"
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand("copy")
      document.body.removeChild(textarea)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={handleCopy}
          className="text-muted-foreground hover:text-foreground"
        >
          {copied ? (
            <CheckCircle2 className="h-3 w-3 text-green-600" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="text-xs">
        {copied ? "Copied!" : "Copy"}
      </TooltipContent>
    </Tooltip>
  )
}

function SecretValue({ value, label }: { value: string; label: string }) {
  const [show, setShow] = useState(false)

  return (
    <div className="flex items-center gap-1.5">
      <code className="max-w-[220px] truncate rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
        {show ? value : "••••••••••••"}
      </code>
      <button
        onClick={(e) => { e.stopPropagation(); setShow(!show) }}
        className="text-muted-foreground hover:text-foreground"
      >
        {show ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
      </button>
      {show && <CopyButton value={value} />}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Empty state (no workspaces)                                        */
/* ------------------------------------------------------------------ */

function NoWorkspaceView() {
  const router = useRouter()
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 py-20">
      <Container className="h-14 w-14 text-muted-foreground" />
      <h2 className="text-lg font-semibold">No Workspace Available</h2>
      <p className="text-sm text-muted-foreground text-center max-w-md">
        Create a workspace to start collaborating with your team.
        You can deploy services, analyze data, and manage resources
        in a shared environment.
      </p>
      <Button onClick={() => router.push("/dashboard/workspaces")}>
        Create Workspace
      </Button>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Expandable Service Row                                             */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  OpenShift-style Data List                                          */
/* ------------------------------------------------------------------ */

function DetailRow({
  label,
  value,
  secret,
  link,
}: {
  label: string
  value: string
  secret?: boolean
  link?: boolean
}) {
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="w-28 shrink-0 text-xs font-medium text-muted-foreground">
        {label}
      </span>
      {secret ? (
        <SecretValue value={value} label={label} />
      ) : link ? (
        <div className="flex items-center gap-1.5 min-w-0">
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 truncate text-xs text-blue-600 hover:underline dark:text-blue-400"
            onClick={(e) => e.stopPropagation()}
          >
            {value}
            <ExternalLink className="h-3 w-3 shrink-0" />
          </a>
          <CopyButton value={value} />
        </div>
      ) : (
        <div className="flex items-center gap-1.5 min-w-0">
          <code className="truncate rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
            {value}
          </code>
          <CopyButton value={value} />
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Service Configuration Sheet (MariaDB, PostgreSQL)                  */
/* ------------------------------------------------------------------ */

const CONFIGURABLE_PLUGINS = new Set([
  "argus-mariadb", "argus-postgresql", "argus-trino", "argus-starrocks", "argus-kafka", "argus-nifi",
  "argus-jupyter", "argus-jupyter-tensorflow", "argus-jupyter-pyspark",
  "argus-mlflow", "argus-airflow", "argus-ollama", "argus-vscode-server",
])

function ServiceConfigSheet({
  open,
  onOpenChange,
  workspaceId,
  service,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: number
  service: WorkspaceService
}) {
  const [options, setOptions] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setSaved(false)
    setError(null)
    authFetch(`/api/v1/workspace/workspaces/${workspaceId}/services/${service.id}/config`)
      .then((res) => res.ok ? res.json() : { options: {} })
      .then((data) => { setOptions(data.options ?? {}); setLoading(false) })
      .catch(() => setLoading(false))
  }, [open, workspaceId, service.id])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/services/${service.id}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ options }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Failed: ${res.status}`)
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save")
    }
    setSaving(false)
  }

  const updateOption = (key: string, value: string) => {
    setOptions((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  // Group options by category based on plugin
  const isMariadb = service.plugin_name === "argus-mariadb"
  const isPostgresql = service.plugin_name === "argus-postgresql"
  const isJupyter = service.plugin_name.startsWith("argus-jupyter")
  const isMlflow = service.plugin_name === "argus-mlflow"
  const isAirflow = service.plugin_name === "argus-airflow"
  const pluginLabel = isMariadb ? "MariaDB" : isPostgresql ? "PostgreSQL" : isMlflow ? "MLflow" : isAirflow ? "Airflow" : "JupyterLab"

  const groups: { title: string; keys: string[] }[] = isMariadb
    ? [
        { title: "Connection", keys: ["max_connections", "wait_timeout", "interactive_timeout", "connect_timeout", "max_allowed_packet", "thread_cache_size"] },
        { title: "Performance", keys: ["innodb_buffer_pool_size", "innodb_log_file_size", "innodb_flush_log_at_trx_commit", "tmp_table_size", "sort_buffer_size", "join_buffer_size"] },
        { title: "Logging", keys: ["slow_query_log", "long_query_time"] },
        { title: "Character Set", keys: ["character_set_server", "collation_server"] },
      ]
    : isPostgresql
    ? [
        { title: "Connection", keys: ["max_connections"] },
        { title: "Memory", keys: ["shared_buffers", "work_mem", "maintenance_work_mem", "effective_cache_size", "wal_buffers", "temp_buffers"] },
        { title: "Performance", keys: ["checkpoint_completion_target", "random_page_cost", "effective_io_concurrency", "default_statistics_target"] },
        { title: "Logging", keys: ["log_min_duration_statement", "log_statement"] },
      ]
    : isMlflow
    ? [
        { title: "Performance", keys: ["MLFLOW_WORKERS", "GUNICORN_CMD_ARGS"] },
        { title: "Server", keys: ["MLFLOW_LOGGING_LEVEL", "MLFLOW_SERVE_ARTIFACTS"] },
      ]
    : isAirflow
    ? [
        { title: "Core", keys: ["AIRFLOW__CORE__PARALLELISM", "AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG", "AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG", "AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION", "AIRFLOW__CORE__DEFAULT_TIMEZONE", "AIRFLOW__CORE__DAG_FILE_PROCESSOR_TIMEOUT"] },
        { title: "Scheduler", keys: ["AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL", "AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL", "AIRFLOW__SCHEDULER__PARSING_PROCESSES", "AIRFLOW__SCHEDULER__SCHEDULER_HEARTBEAT_SEC"] },
        { title: "Webserver", keys: ["AIRFLOW__WEBSERVER__WEB_SERVER_WORKER_TIMEOUT", "AIRFLOW__WEBSERVER__DEFAULT_UI_TIMEZONE", "AIRFLOW__WEBSERVER__HIDE_PAUSED_DAGS_BY_DEFAULT", "AIRFLOW__WEBSERVER__PAGE_SIZE", "AIRFLOW__WEBSERVER__DEFAULT_DAG_RUN_DISPLAY_NUMBER", "AIRFLOW__WEBSERVER__WORKERS"] },
        { title: "Logging", keys: ["AIRFLOW__LOGGING__LOGGING_LEVEL", "AIRFLOW__LOGGING__FAB_LOGGING_LEVEL"] },
        { title: "SMTP", keys: ["AIRFLOW__SMTP__SMTP_HOST", "AIRFLOW__SMTP__SMTP_PORT", "AIRFLOW__SMTP__SMTP_STARTTLS", "AIRFLOW__SMTP__SMTP_SSL", "AIRFLOW__SMTP__SMTP_USER", "AIRFLOW__SMTP__SMTP_PASSWORD", "AIRFLOW__SMTP__SMTP_MAIL_FROM"] },
      ]
    : [
        { title: "Server", keys: ["ServerApp.max_body_size", "ServerApp.max_buffer_size", "ServerApp.shutdown_no_activity_timeout", "ServerApp.terminals_enabled"] },
        { title: "Kernel", keys: ["MappingKernelManager.cull_idle_timeout", "MappingKernelManager.cull_interval", "MappingKernelManager.cull_connected", "MappingKernelManager.default_kernel_name"] },
        { title: "Contents", keys: ["ContentsManager.allow_hidden"] },
      ]

  const renderGroup = (title: string, keys: string[]) => {
    const activeKeys = keys.filter((k) => k in options)
    if (activeKeys.length === 0) return null
    return (
      <div key={title} className="space-y-2">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{title}</h4>
        {activeKeys.map((key) => (
          <div key={key} className="flex items-center gap-3">
            <Label className="w-48 shrink-0 text-xs font-mono">{key}</Label>
            <Input
              className="h-8 text-sm"
              value={options[key] ?? ""}
              onChange={(e) => updateOption(key, e.target.value)}
            />
          </div>
        ))}
      </div>
    )
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[450px] overflow-y-auto sm:max-w-[450px] px-6">
        <SheetHeader className="pb-4">
          <SheetTitle>{pluginLabel} Configuration</SheetTitle>
          <SheetDescription>Edit configuration options. Changes will restart the service.</SheetDescription>
        </SheetHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-5">
            {groups.map((g) => renderGroup(g.title, g.keys))}

            {error && (
              <div className="rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm dark:bg-red-950 dark:text-red-200 dark:border-red-800">
                {error}
              </div>
            )}
            {saved && (
              <div className="rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-2 text-sm dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800">
                Configuration updated. MariaDB is restarting.
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button size="sm" onClick={handleSave} disabled={saving}>
                {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                Apply & Restart
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

// ---------------------------------------------------------------------------
// Trino Configuration Dialog
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// StarRocks Configuration Dialog
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Kafka Configuration Dialog
// ---------------------------------------------------------------------------

function KafkaConfigDialog({
  open, onOpenChange, workspaceId, service,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: number
  service: WorkspaceService
}) {
  const meta = (service.metadata ?? {}) as Record<string, any>
  const resources = meta.resources ?? {}

  // Resources
  const [replicas, setReplicas] = useState(Number(meta.display?.Brokers) || 1)
  const [cpuLimit, setCpuLimit] = useState(resources.cpu_limit || "1")
  const [memLimit, setMemLimit] = useState(resources.memory_limit || "2Gi")
  // Broker
  const [numPartitions, setNumPartitions] = useState("1")
  const [defaultReplicationFactor, setDefaultReplicationFactor] = useState("1")
  const [minInsyncReplicas, setMinInsyncReplicas] = useState("1")
  const [autoCreateTopics, setAutoCreateTopics] = useState(true)
  // Retention
  const [logRetentionHours, setLogRetentionHours] = useState("168")
  const [logRetentionBytes, setLogRetentionBytes] = useState("-1")
  const [logSegmentBytes, setLogSegmentBytes] = useState("1073741824")
  // Performance
  const [numIoThreads, setNumIoThreads] = useState("8")
  const [numNetworkThreads, setNumNetworkThreads] = useState("3")
  const [messageMaxBytes, setMessageMaxBytes] = useState("1048588")
  // Buffer
  const [socketSendBuffer, setSocketSendBuffer] = useState("102400")
  const [socketReceiveBuffer, setSocketReceiveBuffer] = useState("102400")
  const [socketRequestMax, setSocketRequestMax] = useState("104857600")

  const [applying, setApplying] = useState(false)
  const [validation, setValidation] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  // Validate resources
  useEffect(() => {
    if (!open) return
    const timer = setTimeout(async () => {
      try {
        const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/services/${service.id}/configure/validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cpu_limit: cpuLimit, memory_limit: memLimit }),
        })
        if (res.ok) setValidation(await res.json())
      } catch { /* ignore */ }
    }, 300)
    return () => clearTimeout(timer)
  }, [open, cpuLimit, memLimit, workspaceId, service.id])

  const handleApply = async () => {
    if (validation && !validation.allowed) return
    setApplying(true)
    setError(null)
    setSuccess(false)
    try {
      const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/kafka/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          replicas,
          cpu_limit: cpuLimit,
          memory_limit: memLimit,
          num_partitions: parseInt(numPartitions) || undefined,
          default_replication_factor: parseInt(defaultReplicationFactor) || undefined,
          min_insync_replicas: parseInt(minInsyncReplicas) || undefined,
          auto_create_topics: autoCreateTopics,
          log_retention_hours: parseInt(logRetentionHours) || undefined,
          log_retention_bytes: parseInt(logRetentionBytes),
          log_segment_bytes: parseInt(logSegmentBytes) || undefined,
          num_io_threads: parseInt(numIoThreads) || undefined,
          num_network_threads: parseInt(numNetworkThreads) || undefined,
          message_max_bytes: parseInt(messageMaxBytes) || undefined,
          socket_send_buffer_bytes: parseInt(socketSendBuffer) || undefined,
          socket_receive_buffer_bytes: parseInt(socketReceiveBuffer) || undefined,
          socket_request_max_bytes: parseInt(socketRequestMax) || undefined,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Failed: ${res.status}`)
      }
      setSuccess(true)
      setTimeout(() => { setSuccess(false); onOpenChange(false) }, 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to apply")
    }
    setApplying(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Configure Kafka</DialogTitle>
          <DialogDescription>Adjust Kafka broker settings. Changes trigger a rolling restart.</DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Resources */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Resources</Label>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Brokers</Label>
                <Input type="number" min={1} max={10} value={replicas} onChange={(e) => setReplicas(Number(e.target.value))} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">CPU Limit</Label>
                <Input value={cpuLimit} onChange={(e) => setCpuLimit(e.target.value)} placeholder="e.g. 1, 2" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Memory Limit</Label>
                <Input value={memLimit} onChange={(e) => setMemLimit(e.target.value)} placeholder="e.g. 2Gi" />
              </div>
            </div>
          </div>

          {/* Broker Settings */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Broker</Label>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">num.partitions</Label>
                <Input type="number" min={1} value={numPartitions} onChange={(e) => setNumPartitions(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">Default partitions per new topic</span>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">default.replication.factor</Label>
                <Input type="number" min={1} value={defaultReplicationFactor} onChange={(e) => setDefaultReplicationFactor(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">Default replication for new topics</span>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">min.insync.replicas</Label>
                <Input type="number" min={1} value={minInsyncReplicas} onChange={(e) => setMinInsyncReplicas(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">Min replicas that must ack a write</span>
              </div>
              <div className="flex items-center gap-2 pt-4">
                <input type="checkbox" id="kafka-auto-topics" checked={autoCreateTopics} onChange={(e) => setAutoCreateTopics(e.target.checked)} />
                <Label htmlFor="kafka-auto-topics" className="text-xs cursor-pointer">auto.create.topics</Label>
              </div>
            </div>
          </div>

          {/* Retention */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Retention</Label>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">log.retention.hours</Label>
                <Input type="number" value={logRetentionHours} onChange={(e) => setLogRetentionHours(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">Message retention (hours)</span>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">log.retention.bytes</Label>
                <Input value={logRetentionBytes} onChange={(e) => setLogRetentionBytes(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">-1 = unlimited</span>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">log.segment.bytes</Label>
                <Input value={logSegmentBytes} onChange={(e) => setLogSegmentBytes(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">Segment file size</span>
              </div>
            </div>
          </div>

          {/* Performance */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Performance</Label>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">num.io.threads</Label>
                <Input type="number" min={1} value={numIoThreads} onChange={(e) => setNumIoThreads(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">Disk I/O threads</span>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">num.network.threads</Label>
                <Input type="number" min={1} value={numNetworkThreads} onChange={(e) => setNumNetworkThreads(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">Network handler threads</span>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">message.max.bytes</Label>
                <Input value={messageMaxBytes} onChange={(e) => setMessageMaxBytes(e.target.value)} />
                <span className="text-[10px] text-muted-foreground">Max message size</span>
              </div>
            </div>
          </div>

          {/* Buffer / Socket */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Socket / Buffer</Label>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">socket.send.buffer</Label>
                <Input value={socketSendBuffer} onChange={(e) => setSocketSendBuffer(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">socket.receive.buffer</Label>
                <Input value={socketReceiveBuffer} onChange={(e) => setSocketReceiveBuffer(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">socket.request.max</Label>
                <Input value={socketRequestMax} onChange={(e) => setSocketRequestMax(e.target.value)} />
              </div>
            </div>
          </div>

          {/* Validation */}
          {validation && (
            <div className={`rounded-md border px-3 py-2 text-xs ${validation.allowed ? "bg-muted/30" : "bg-destructive/10 border-destructive/30 text-destructive"}`}>
              <div className="flex justify-between">
                <span>CPU: {validation.after?.cpu_used} / {validation.limit?.cpu} cores</span>
                <span>Memory: {validation.after?.memory_used_gb} / {validation.limit?.memory_gb} GiB</span>
              </div>
              {!validation.allowed && <div className="mt-1 font-medium">{validation.message}</div>}
            </div>
          )}

          {error && <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-xs text-destructive">{error}</div>}
          {success && <div className="rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-700">Restarting the service with the requested resources.</div>}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button size="sm" onClick={handleApply} disabled={applying || (validation && !validation.allowed)}>
            {applying ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Apply
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

const STARROCKS_TIERS = [
  { tier: "development", label: "Development", be: 1, feCpu: "1", feMem: "2Gi", beCpu: "2", beMem: "4Gi" },
  { tier: "standard", label: "Standard", be: 3, feCpu: "2", feMem: "4Gi", beCpu: "2", beMem: "4Gi" },
  { tier: "performance", label: "Performance", be: 5, feCpu: "2", feMem: "4Gi", beCpu: "4", beMem: "8Gi" },
]

function StarRocksConfigDialog({
  open, onOpenChange, workspaceId, service,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: number
  service: WorkspaceService
}) {
  const meta = (service.metadata ?? {}) as Record<string, any>
  const display = meta.display ?? {}
  const resources = meta.resources ?? {}

  const [tier, setTier] = useState(display.Tier?.toLowerCase() || "development")
  const [beReplicas, setBeReplicas] = useState(Number(display["Backend Nodes"]) || 1)
  const [feCpu, setFeCpu] = useState(resources.cpu_limit || "2")
  const [feMem, setFeMem] = useState(resources.memory_limit || "4Gi")
  const [beCpu, setBeCpu] = useState(resources.be_cpu_limit || "2")
  const [beMem, setBeMem] = useState(resources.be_memory_limit || "4Gi")

  const [applying, setApplying] = useState(false)
  const [validation, setValidation] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleTierChange = (t: string) => {
    setTier(t)
    const preset = STARROCKS_TIERS.find((p) => p.tier === t)
    if (preset) {
      setBeReplicas(preset.be)
      setFeCpu(preset.feCpu)
      setFeMem(preset.feMem)
      setBeCpu(preset.beCpu)
      setBeMem(preset.beMem)
    }
  }

  // Validate
  useEffect(() => {
    if (!open) return
    const timer = setTimeout(async () => {
      try {
        const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/services/${service.id}/configure/validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cpu_limit: feCpu, memory_limit: feMem }),
        })
        if (res.ok) setValidation(await res.json())
      } catch { /* ignore */ }
    }, 300)
    return () => clearTimeout(timer)
  }, [open, feCpu, feMem, beCpu, beMem, beReplicas, workspaceId, service.id])

  const handleApply = async () => {
    if (validation && !validation.allowed) return
    setApplying(true)
    setError(null)
    setSuccess(false)
    try {
      const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/starrocks/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tier, be_replicas: beReplicas,
          fe_cpu_limit: feCpu, fe_memory_limit: feMem,
          be_cpu_limit: beCpu, be_memory_limit: beMem,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Failed: ${res.status}`)
      }
      setSuccess(true)
      setTimeout(() => { setSuccess(false); onOpenChange(false) }, 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to apply")
    }
    setApplying(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Configure StarRocks</DialogTitle>
          <DialogDescription>
            Adjust StarRocks cluster. <span className="normal-case font-normal">(Current: {display.Tier || "Unknown"})</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Tier */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Tier</Label>
            <div className="grid grid-cols-4 gap-2">
              {[...STARROCKS_TIERS, { tier: "custom", label: "Custom", be: 0, feCpu: "", feMem: "", beCpu: "", beMem: "" }].map((t) => (
                <button
                  key={t.tier}
                  onClick={() => handleTierChange(t.tier)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                    tier === t.tier ? "border-primary bg-primary/10 text-primary" : "hover:bg-muted/50"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* BE Replicas */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Backend Nodes</Label>
            <Input type="number" min={1} max={10} value={beReplicas}
              onChange={(e) => { setBeReplicas(Number(e.target.value)); setTier("custom") }} />
          </div>

          {/* Resources */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Resources</Label>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">FE CPU Limit</Label>
                <Input value={feCpu} onChange={(e) => { setFeCpu(e.target.value); setTier("custom") }} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">FE Memory Limit</Label>
                <Input value={feMem} onChange={(e) => { setFeMem(e.target.value); setTier("custom") }} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">BE CPU Limit</Label>
                <Input value={beCpu} onChange={(e) => { setBeCpu(e.target.value); setTier("custom") }} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">BE Memory Limit</Label>
                <Input value={beMem} onChange={(e) => { setBeMem(e.target.value); setTier("custom") }} />
              </div>
            </div>
          </div>

          {/* Validation */}
          {validation && (
            <div className={`rounded-md border px-3 py-2 text-xs ${validation.allowed ? "bg-muted/30" : "bg-destructive/10 border-destructive/30 text-destructive"}`}>
              <div className="flex justify-between">
                <span>CPU: {validation.after?.cpu_used} / {validation.limit?.cpu} cores</span>
                <span>Memory: {validation.after?.memory_used_gb} / {validation.limit?.memory_gb} GiB</span>
              </div>
              {!validation.allowed && <div className="mt-1 font-medium">{validation.message}</div>}
            </div>
          )}

          {error && <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-xs text-destructive">{error}</div>}
          {success && <div className="rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-700">Restarting the service with the requested resources.</div>}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button size="sm" onClick={handleApply} disabled={applying || (validation && !validation.allowed)}>
            {applying ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Apply
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

const TRINO_TIERS = [
  { tier: "development", label: "Development", coord: 1, workers: 0, coordCpu: "1", coordMem: "2Gi", workerCpu: "1", workerMem: "2Gi" },
  { tier: "standard", label: "Standard", coord: 1, workers: 1, coordCpu: "1", coordMem: "2Gi", workerCpu: "2", workerMem: "4Gi" },
  { tier: "performance", label: "Performance", coord: 2, workers: 3, coordCpu: "1", coordMem: "2Gi", workerCpu: "2", workerMem: "4Gi" },
]

function TrinoConfigDialog({
  open, onOpenChange, workspaceId, service,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: number
  service: WorkspaceService
}) {
  const meta = (service.metadata ?? {}) as Record<string, any>
  const display = meta.display ?? {}
  const resources = meta.resources ?? {}

  const [tier, setTier] = useState(display.Tier?.toLowerCase() || "standard")
  const [coordReplicas, setCoordReplicas] = useState(Number(display.Coordinators) || 1)
  const [workerReplicas, setWorkerReplicas] = useState(Number(display.Workers) || 1)
  const [coordCpu, setCoordCpu] = useState(resources.cpu_limit || "1")
  const [coordMem, setCoordMem] = useState(resources.memory_limit || "2Gi")
  const [workerCpu, setWorkerCpu] = useState(resources.worker_cpu_limit || "2")
  const [workerMem, setWorkerMem] = useState(resources.worker_memory_limit || "4Gi")
  const [queryMax, setQueryMax] = useState("1GB")
  const [queryMaxNode, setQueryMaxNode] = useState("512MB")
  const [refreshCatalogs, setRefreshCatalogs] = useState(false)

  const [applying, setApplying] = useState(false)
  const [validation, setValidation] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  // When tier changes, apply preset values
  const handleTierChange = (t: string) => {
    setTier(t)
    const preset = TRINO_TIERS.find((p) => p.tier === t)
    if (preset) {
      setCoordReplicas(preset.coord)
      setWorkerReplicas(preset.workers)
      setCoordCpu(preset.coordCpu)
      setCoordMem(preset.coordMem)
      setWorkerCpu(preset.workerCpu)
      setWorkerMem(preset.workerMem)
    }
  }

  // Validate on any change
  useEffect(() => {
    if (!open) return
    const timer = setTimeout(async () => {
      try {
        const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/trino/configure/validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            coordinator_replicas: coordReplicas,
            worker_replicas: workerReplicas,
            coordinator_cpu_limit: coordCpu,
            coordinator_memory_limit: coordMem,
            worker_cpu_limit: workerCpu,
            worker_memory_limit: workerMem,
          }),
        })
        if (res.ok) setValidation(await res.json())
      } catch { /* ignore */ }
    }, 300)
    return () => clearTimeout(timer)
  }, [open, coordReplicas, workerReplicas, coordCpu, coordMem, workerCpu, workerMem, workspaceId])

  const handleApply = async () => {
    if (validation && !validation.allowed) return
    setApplying(true)
    setError(null)
    setSuccess(false)
    try {
      const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/trino/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tier,
          coordinator_replicas: coordReplicas,
          worker_replicas: workerReplicas,
          coordinator_cpu_limit: coordCpu,
          coordinator_memory_limit: coordMem,
          worker_cpu_limit: workerCpu,
          worker_memory_limit: workerMem,
          query_max_memory: queryMax,
          query_max_memory_per_node: queryMaxNode,
          refresh_catalogs: refreshCatalogs,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Failed: ${res.status}`)
      }
      setSuccess(true)
      setTimeout(() => { setSuccess(false); onOpenChange(false) }, 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to apply")
    }
    setApplying(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Configure Trino</DialogTitle>
          <DialogDescription>Adjust Trino cluster configuration. Changes trigger a pod restart.</DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Tier */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">
              Tier <span className="normal-case font-normal">(Current: {display.Tier || "Unknown"})</span>
            </Label>
            <div className="grid grid-cols-4 gap-2">
              {[...TRINO_TIERS, { tier: "custom", label: "Custom", coord: 0, workers: 0, coordCpu: "", coordMem: "", workerCpu: "", workerMem: "" }].map((t) => (
                <button
                  key={t.tier}
                  onClick={() => handleTierChange(t.tier)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                    tier === t.tier ? "border-primary bg-primary/10 text-primary" : "hover:bg-muted/50"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Replicas */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Replicas</Label>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Coordinators</Label>
                <Input type="number" min={1} max={3} value={coordReplicas}
                  onChange={(e) => { setCoordReplicas(Number(e.target.value)); setTier("custom") }} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Workers</Label>
                <Input type="number" min={0} max={10} value={workerReplicas}
                  onChange={(e) => { setWorkerReplicas(Number(e.target.value)); setTier("custom") }} />
              </div>
            </div>
          </div>

          {/* Resources */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Resources</Label>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Coordinator CPU Limit</Label>
                <Input value={coordCpu} onChange={(e) => { setCoordCpu(e.target.value); setTier("custom") }} placeholder="e.g. 1, 2, 500m" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Coordinator Memory Limit</Label>
                <Input value={coordMem} onChange={(e) => { setCoordMem(e.target.value); setTier("custom") }} placeholder="e.g. 2Gi, 4Gi" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Worker CPU Limit</Label>
                <Input value={workerCpu} onChange={(e) => { setWorkerCpu(e.target.value); setTier("custom") }} placeholder="e.g. 2, 4" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Worker Memory Limit</Label>
                <Input value={workerMem} onChange={(e) => { setWorkerMem(e.target.value); setTier("custom") }} placeholder="e.g. 4Gi, 8Gi" />
              </div>
            </div>
          </div>

          {/* Query Limits */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Query Limits</Label>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Max Memory</Label>
                <Input value={queryMax} onChange={(e) => setQueryMax(e.target.value)} placeholder="e.g. 1GB, 4GB" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Max Memory Per Node</Label>
                <Input value={queryMaxNode} onChange={(e) => setQueryMaxNode(e.target.value)} placeholder="e.g. 512MB, 2GB" />
              </div>
            </div>
          </div>

          {/* Catalogs */}
          <div className="flex items-center gap-3">
            <input type="checkbox" id="refresh-catalogs" checked={refreshCatalogs} onChange={(e) => setRefreshCatalogs(e.target.checked)} />
            <Label htmlFor="refresh-catalogs" className="text-sm cursor-pointer">Refresh Catalogs (re-detect workspace DB services)</Label>
          </div>

          {/* Resource validation */}
          {validation && (
            <div className={`rounded-md border px-3 py-2 text-xs ${validation.allowed ? "bg-muted/30" : "bg-destructive/10 border-destructive/30 text-destructive"}`}>
              <div className="flex justify-between">
                <span>CPU: {validation.after.cpu_used} / {validation.limit.cpu} cores</span>
                <span>Memory: {validation.after.memory_used_gb} / {validation.limit.memory_gb} GiB</span>
              </div>
              {validation.delta.cpu !== 0 && (
                <div className="text-muted-foreground mt-1">
                  Change: {validation.delta.cpu > 0 ? "+" : ""}{validation.delta.cpu} CPU, {validation.delta.memory_gb > 0 ? "+" : ""}{validation.delta.memory_gb} GiB
                </div>
              )}
              {!validation.allowed && <div className="mt-1 font-medium">{validation.message}</div>}
            </div>
          )}

          {error && <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-xs text-destructive">{error}</div>}
          {success && <div className="rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-700">Configuration applied. Pods are restarting.</div>}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button size="sm" onClick={handleApply} disabled={applying || (validation && !validation.allowed)}>
            {applying ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Apply
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Generic Service Configuration Dialog (PostgreSQL, MariaDB, Ollama, Jupyter, VS Code, MLflow)
// ---------------------------------------------------------------------------

function ServiceConfigDialog({
  open, onOpenChange, workspaceId, service,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: number
  service: WorkspaceService
}) {
  const meta = (service.metadata ?? {}) as Record<string, any>
  const resources = meta.resources ?? {}
  const plugin = service.plugin_name

  const isPg = plugin === "argus-postgresql"
  const isMaria = plugin === "argus-mariadb"
  const isOllama = plugin === "argus-ollama"
  const isDb = isPg || isMaria

  // Resource fields
  const [cpuLimit, setCpuLimit] = useState(resources.cpu_limit || "2")
  const [memLimit, setMemLimit] = useState(resources.memory_limit || "2Gi")

  // PostgreSQL fields
  const [maxConnections, setMaxConnections] = useState("100")
  const [sharedBuffers, setSharedBuffers] = useState("128MB")
  const [workMem, setWorkMem] = useState("4MB")
  const [effectiveCacheSize, setEffectiveCacheSize] = useState("512MB")
  const [maintenanceWorkMem, setMaintenanceWorkMem] = useState("64MB")
  const [logMinDuration, setLogMinDuration] = useState("-1")
  const [logStatement, setLogStatement] = useState("none")

  // MariaDB fields
  const [innodbBufferPool, setInnodbBufferPool] = useState("128MB")
  const [slowQueryLog, setSlowQueryLog] = useState(false)
  const [longQueryTime, setLongQueryTime] = useState("10")

  // Ollama
  const [defaultModel, setDefaultModel] = useState(meta.display?.["Default Model"] || "")

  // Common
  const [regenPassword, setRegenPassword] = useState(false)
  const [applying, setApplying] = useState(false)
  const [validation, setValidation] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  // Validate on resource change
  useEffect(() => {
    if (!open) return
    const timer = setTimeout(async () => {
      try {
        const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/services/${service.id}/configure/validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cpu_limit: cpuLimit, memory_limit: memLimit }),
        })
        if (res.ok) setValidation(await res.json())
      } catch { /* ignore */ }
    }, 300)
    return () => clearTimeout(timer)
  }, [open, cpuLimit, memLimit, workspaceId, service.id])

  const handleApply = async () => {
    if (validation && !validation.allowed) return
    setApplying(true)
    setError(null)
    setSuccess(false)
    try {
      // First validate with all fields
      const validateRes = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/services/${service.id}/configure/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cpu_limit: cpuLimit,
          memory_limit: memLimit,
          ...(isPg ? {
            max_connections: parseInt(maxConnections) || undefined,
            shared_buffers: sharedBuffers || undefined,
            work_mem: workMem || undefined,
            effective_cache_size: effectiveCacheSize || undefined,
            maintenance_work_mem: maintenanceWorkMem || undefined,
            log_min_duration_statement: parseInt(logMinDuration),
            log_statement: logStatement,
          } : {}),
          ...(isMaria ? {
            max_connections: parseInt(maxConnections) || undefined,
            innodb_buffer_pool_size: innodbBufferPool || undefined,
            slow_query_log: slowQueryLog,
            long_query_time: parseInt(longQueryTime) || undefined,
          } : {}),
        }),
      })
      const valData = await validateRes.json()
      if (!valData.allowed) {
        setError(valData.message || "Validation failed")
        setApplying(false)
        return
      }

      // Apply
      const body: Record<string, any> = {
        cpu_limit: cpuLimit,
        memory_limit: memLimit,
        regenerate_password: regenPassword,
      }
      if (isPg) {
        body.max_connections = parseInt(maxConnections) || undefined
        body.shared_buffers = sharedBuffers || undefined
        body.work_mem = workMem || undefined
        body.effective_cache_size = effectiveCacheSize || undefined
        body.maintenance_work_mem = maintenanceWorkMem || undefined
        body.log_min_duration_statement = parseInt(logMinDuration)
        body.log_statement = logStatement
      }
      if (isMaria) {
        body.max_connections = parseInt(maxConnections) || undefined
        body.innodb_buffer_pool_size = innodbBufferPool || undefined
        body.slow_query_log = slowQueryLog
        body.long_query_time = parseInt(longQueryTime) || undefined
      }
      if (isOllama && defaultModel) {
        body.default_model = defaultModel
      }

      const res = await authFetch(`/api/v1/workspace/workspaces/${workspaceId}/services/${service.id}/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Failed: ${res.status}`)
      }
      setSuccess(true)
      setTimeout(() => { setSuccess(false); onOpenChange(false) }, 2500)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to apply")
    }
    setApplying(false)
  }

  const pluginLabel = {
    "argus-postgresql": "PostgreSQL",
    "argus-mariadb": "MariaDB",
    "argus-ollama": "Ollama",
    "argus-jupyter": "JupyterLab",
    "argus-jupyter-tensorflow": "JupyterLab (TensorFlow)",
    "argus-jupyter-pyspark": "JupyterLab (PySpark)",
    "argus-mlflow": "MLflow",
    "argus-airflow": "Airflow",
    "argus-vscode-server": "VS Code Server",
  }[plugin] || service.display_name || plugin

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Configure {pluginLabel}</DialogTitle>
          <DialogDescription>Adjust resources and settings. Changes are applied immediately.</DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Resources — common for all */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">Resources</Label>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">CPU Limit</Label>
                <Input value={cpuLimit} onChange={(e) => setCpuLimit(e.target.value)} placeholder="e.g. 2, 500m" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Memory Limit</Label>
                <Input value={memLimit} onChange={(e) => setMemLimit(e.target.value)} placeholder="e.g. 2Gi, 512Mi" />
              </div>
            </div>
          </div>

          {/* PostgreSQL specific */}
          {isPg && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">Performance</Label>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs">max_connections</Label>
                  <Input type="number" value={maxConnections} onChange={(e) => setMaxConnections(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">shared_buffers</Label>
                  <Input value={sharedBuffers} onChange={(e) => setSharedBuffers(e.target.value)} placeholder="128MB" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">work_mem</Label>
                  <Input value={workMem} onChange={(e) => setWorkMem(e.target.value)} placeholder="4MB" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">effective_cache_size</Label>
                  <Input value={effectiveCacheSize} onChange={(e) => setEffectiveCacheSize(e.target.value)} placeholder="512MB" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">maintenance_work_mem</Label>
                  <Input value={maintenanceWorkMem} onChange={(e) => setMaintenanceWorkMem(e.target.value)} placeholder="64MB" />
                </div>
              </div>
              <Label className="text-xs font-semibold uppercase text-muted-foreground mt-3">Logging</Label>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs">log_min_duration_statement (ms)</Label>
                  <Input type="number" value={logMinDuration} onChange={(e) => setLogMinDuration(e.target.value)} placeholder="-1 = off" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">log_statement</Label>
                  <select className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={logStatement} onChange={(e) => setLogStatement(e.target.value)}>
                    <option value="none">none</option>
                    <option value="ddl">ddl</option>
                    <option value="mod">mod</option>
                    <option value="all">all</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* MariaDB specific */}
          {isMaria && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">Performance</Label>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs">max_connections</Label>
                  <Input type="number" value={maxConnections} onChange={(e) => setMaxConnections(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">innodb_buffer_pool_size</Label>
                  <Input value={innodbBufferPool} onChange={(e) => setInnodbBufferPool(e.target.value)} placeholder="128MB" />
                </div>
              </div>
              <Label className="text-xs font-semibold uppercase text-muted-foreground mt-3">Logging</Label>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center gap-2">
                  <input type="checkbox" id="slow-query" checked={slowQueryLog} onChange={(e) => setSlowQueryLog(e.target.checked)} />
                  <Label htmlFor="slow-query" className="text-xs cursor-pointer">slow_query_log</Label>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">long_query_time (sec)</Label>
                  <Input type="number" value={longQueryTime} onChange={(e) => setLongQueryTime(e.target.value)} />
                </div>
              </div>
            </div>
          )}

          {/* Ollama specific */}
          {isOllama && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase text-muted-foreground">Model</Label>
              <div className="space-y-1">
                <Label className="text-xs">Default Model</Label>
                <Input value={defaultModel} onChange={(e) => setDefaultModel(e.target.value)} placeholder="e.g. llama3.2:1b" />
              </div>
            </div>
          )}

          {/* Password regeneration — DB services only */}
          {isDb && (
            <div className="flex items-center gap-3">
              <input type="checkbox" id="regen-pw" checked={regenPassword} onChange={(e) => setRegenPassword(e.target.checked)} />
              <Label htmlFor="regen-pw" className="text-sm cursor-pointer">Regenerate password</Label>
            </div>
          )}

          {/* Validation display */}
          {validation && (
            <div className={`rounded-md border px-3 py-2 text-xs ${validation.allowed ? "bg-muted/30" : "bg-destructive/10 border-destructive/30 text-destructive"}`}>
              {validation.validation_errors ? (
                <ul className="list-disc pl-4 space-y-0.5">
                  {validation.validation_errors.map((e: string, i: number) => <li key={i}>{e}</li>)}
                </ul>
              ) : (
                <>
                  <div className="flex justify-between">
                    <span>CPU: {validation.after?.cpu_used} / {validation.limit?.cpu} cores</span>
                    <span>Memory: {validation.after?.memory_used_gb} / {validation.limit?.memory_gb} GiB</span>
                  </div>
                  {!validation.allowed && <div className="mt-1 font-medium">{validation.message}</div>}
                </>
              )}
            </div>
          )}

          {error && <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-xs text-destructive">{error}</div>}
          {success && <div className="rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-700">Restarting the service with the requested resources.</div>}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button size="sm" onClick={handleApply} disabled={applying || (validation && !validation.allowed && !validation.validation_errors)}>
            {applying ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Apply
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ServiceDataListItem({
  service,
  hideTimestamps,
  onDelete,
  workspaceId,
  workspaceName,
}: {
  service: WorkspaceService
  hideTimestamps?: boolean
  onDelete?: (service: WorkspaceService) => void
  workspaceId?: number
  workspaceName?: string
}) {
  const [expanded, setExpanded] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [configOpen, setConfigOpen] = useState(false)
  const [logsOpen, setLogsOpen] = useState(false)
  const isConfigurable = CONFIGURABLE_PLUGINS.has(service.plugin_name)
  // Map plugin_name to icon filename
  const PLUGIN_ICON_MAP: Record<string, string> = {
    "argus-vscode-server": "code",
    "argus-minio": "minio",
    "argus-minio-deploy": "minio",
  }
  const iconName = PLUGIN_ICON_MAP[service.plugin_name]
    ?? service.plugin_name.replace(/^argus-/, "").replace(/-deploy$/, "")
  const meta = service.metadata ?? {}

  // Extract display metadata (new format: metadata.display)
  // Falls back to flat metadata for backward compatibility
  const displayMeta: Record<string, unknown> =
    meta.display && typeof meta.display === "object" && !Array.isArray(meta.display)
      ? (meta.display as Record<string, unknown>)
      : (() => {
          // Legacy flat format: exclude known internal keys
          const internalKeys = new Set([
            "internal", "display", "namespace",
            "internal_endpoint", "internal_bolt", "internal_http",
            "internal_grpc", "internal_attu", "internal_mysql", "internal_mongodb",
            "bolt_port", "http_port", "grpc_port", "attu_port",
            "mysql_port", "mongodb_port", "project_id",
          ])
          const result: Record<string, unknown> = {}
          for (const [k, v] of Object.entries(meta)) {
            if (!internalKeys.has(k) && v != null && v !== "") result[k] = v
          }
          return result
        })()

  // Determine display URL: prefer display metadata URLs, then endpoint
  // Prefer service.endpoint as primary URL, fallback to first HTTP URL in display metadata
  const endpointIsHttp = service.endpoint && /^https?:\/\//.test(service.endpoint)
  const firstHttpUrl = endpointIsHttp
    ? service.endpoint
    : (Object.values(displayMeta).find(
        (v) => typeof v === "string" && /^https?:\/\//.test(v),
      ) as string | undefined)
  const displayUrl = firstHttpUrl || service.endpoint
  const openUrl = firstHttpUrl || null

  // Custom labels (injected by GitLab default service mapping)
  const svcAny = service as WorkspaceService & { _usernameLabel?: string; _passwordLabel?: string; _hideUrl?: boolean; _hideTimestamps?: boolean }
  const usernameLabel = svcAny._usernameLabel || "Username"
  const passwordLabel = svcAny._passwordLabel || "Password"
  const hideUrl = svcAny._hideUrl || false
  const effectiveHideTimestamps = hideTimestamps || svcAny._hideTimestamps || false

  // Collect detail rows for expanded view
  const details: { label: string; value: string; secret?: boolean; link?: boolean }[] = []
  if (service.username) details.push({ label: usernameLabel, value: service.username })
  if (service.password) details.push({ label: passwordLabel, value: service.password, secret: true })
  if (service.access_token) details.push({ label: "Access Token", value: service.access_token, secret: true })
  // Display metadata entries
  for (const [key, val] of Object.entries(displayMeta)) {
    if (val == null || val === "") continue
    const strVal = String(val)
    const isLink = /^https?:\/\//.test(strVal) || /^bolt:\/\//.test(strVal)
    const isSecret = /password/i.test(key)
    details.push({ label: key, value: strVal, link: isLink, secret: isSecret })
  }
  if (!effectiveHideTimestamps) {
    details.push({ label: "Created", value: formatDateTime(service.created_at) })
    if (service.updated_at !== service.created_at) {
      details.push({ label: "Updated", value: formatDateTime(service.updated_at) })
    }
  }

  return (
    <div className="border-b last:border-b-0">
      {/* Collapsed row */}
      <div
        className={`flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/40 ${expanded ? "bg-muted/30" : ""}`}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Chevron */}
        <div className="shrink-0">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>

        {/* Icon + Name */}
        <PluginIcon icon={iconName} size={28} className="shrink-0 rounded" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold">
              {service.display_name || service.plugin_name}
            </span>
            <code className="hidden shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground sm:inline">
              {service.version ? `v${service.version}` : service.plugin_name}
            </code>
          </div>
          {/* Primary URL inline */}
          {displayUrl && !hideUrl && (
            <a
              href={openUrl || displayUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 truncate text-xs text-blue-600 hover:underline dark:text-blue-400"
              onClick={(e) => e.stopPropagation()}
            >
              {displayUrl}
              <ExternalLink className="h-3 w-3 shrink-0" />
            </a>
          )}
        </div>

        {/* Status badge + Open Service */}
        <div className="flex items-center gap-2 shrink-0">
          {statusBadge(service.status)}
          {openUrl && !hideUrl && (
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-6 px-2"
              onClick={async (e) => {
                e.stopPropagation()
                try {
                  const wsName = workspaceName || ""
                  const res = await authFetch(
                    `/api/v1/workspace/workspaces/auth-launch?workspace=${wsName}`
                  )
                  if (!res.ok) throw new Error("Auth failed")
                  const data = await res.json()
                  // Call auth-redirect via the service's parent domain
                  // so the Set-Cookie domain matches *.argus-insight.{domain}
                  let authHost = window.location.hostname + ":4500"
                  try {
                    const svcHost = new URL(openUrl).hostname // e.g. argus-rstudio-xxx.argus-insight.dev.net
                    const parts = svcHost.split(".")
                    if (parts.length > 2) {
                      // Use parent domain: argus-insight.dev.net:4500
                      authHost = parts.slice(1).join(".") + ":4500"
                    }
                  } catch { /* fallback to window.location.hostname */ }
                  const redirectUrl = `http://${authHost}/api/v1/workspace/workspaces/auth-redirect?workspace=${wsName}&token=${data.token}&redirect=${encodeURIComponent(openUrl)}`
                  window.open(redirectUrl, "_blank")
                } catch {
                  window.open(openUrl, "_blank")
                }
              }}
            >
              Open
              <ExternalLink className="ml-1 h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t bg-muted/20 px-4 py-4 pl-14">
          <div className="grid gap-x-10 gap-y-0.5 sm:grid-cols-2">
            {displayUrl && !hideUrl && (
              <DetailRow label="URL" value={displayUrl} link />
            )}
            {details.map((d) => (
              <DetailRow
                key={d.label}
                label={d.label}
                value={d.value}
                secret={d.secret}
                link={d.link}
              />
            ))}
          </div>
          <div className="mt-3 flex items-center justify-end gap-2">
            {workspaceId && service.status === "running" && (
              <Button
                variant={logsOpen ? "secondary" : "outline"}
                size="sm"
                className="text-xs"
                onClick={(e) => { e.stopPropagation(); setLogsOpen(!logsOpen) }}
              >
                <Terminal className="mr-1.5 h-3.5 w-3.5" />
                {logsOpen ? "Hide Logs" : "Logs"}
              </Button>
            )}
            {isConfigurable && workspaceId && (
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={(e) => { e.stopPropagation(); setConfigOpen(true) }}
              >
                <Settings className="mr-1.5 h-3.5 w-3.5" />
                Configure
              </Button>
            )}
            {onDelete && (
              <Button
                variant="destructive"
                size="sm"
                className="text-xs"
                onClick={(e) => { e.stopPropagation(); setConfirmOpen(true) }}
              >
                Delete Service
              </Button>
            )}
          </div>
          {logsOpen && workspaceId && (
            <div className="mt-3">
              <ServiceLogsPanel
                workspaceId={workspaceId}
                service={service}
              />
            </div>
          )}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={confirmOpen} onOpenChange={(open) => { if (!open && !deleting) setConfirmOpen(false) }}>
        <DialogContent className="sm:max-w-sm" onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Delete Service</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this service? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmOpen(false)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={deleting}
              onClick={async () => {
                setDeleting(true)
                try {
                  await onDelete?.(service)
                } finally {
                  setDeleting(false)
                  setConfirmOpen(false)
                }
              }}
            >
              {deleting ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      {/* Service Config Dialog */}
      {isConfigurable && workspaceId && service.plugin_name === "argus-trino" && (
        <TrinoConfigDialog
          open={configOpen}
          onOpenChange={setConfigOpen}
          workspaceId={workspaceId}
          service={service}
        />
      )}
      {isConfigurable && workspaceId && service.plugin_name === "argus-starrocks" && (
        <StarRocksConfigDialog
          open={configOpen}
          onOpenChange={setConfigOpen}
          workspaceId={workspaceId}
          service={service}
        />
      )}
      {isConfigurable && workspaceId && service.plugin_name === "argus-kafka" && (
        <KafkaConfigDialog
          open={configOpen}
          onOpenChange={setConfigOpen}
          workspaceId={workspaceId}
          service={service}
        />
      )}
      {isConfigurable && workspaceId && service.plugin_name !== "argus-trino" && service.plugin_name !== "argus-starrocks" && service.plugin_name !== "argus-kafka" && (
        <ServiceConfigDialog
          open={configOpen}
          onOpenChange={setConfigOpen}
          workspaceId={workspaceId}
          service={service}
        />
      )}
    </div>
  )
}

function ServiceDataList({
  services,
  hideTimestamps,
  onDelete,
  isOwner,
  perUserPlugins,
  workspaceId,
  workspaceName,
}: {
  services: WorkspaceService[]
  hideTimestamps?: boolean
  onDelete?: (service: WorkspaceService) => void
  isOwner?: boolean
  perUserPlugins?: Set<string>
  workspaceId?: number
  workspaceName?: string
}) {
  return (
    <div className="rounded-lg border">
      {services.map((svc) => {
        const canDelete = onDelete
          ? isOwner || (perUserPlugins?.has(svc.plugin_name) ?? false)
          : false
        return (
          <ServiceDataListItem
            key={svc.id}
            service={svc}
            hideTimestamps={hideTimestamps}
            onDelete={canDelete ? onDelete : undefined}
            workspaceId={workspaceId}
            workspaceName={workspaceName}
          />
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Workspace Resource Dashboard                                       */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Add Service Button + Deploy Dialog                                 */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Workspace Members                                                  */
/* ------------------------------------------------------------------ */

function memberInitials(m: WorkspaceMember): string {
  if (m.display_name) {
    const parts = m.display_name.split(" ")
    return parts.length >= 2
      ? (parts[0]![0]! + parts[1]![0]!).toUpperCase()
      : m.display_name.slice(0, 2).toUpperCase()
  }
  return (m.username ?? "?").slice(0, 2).toUpperCase()
}

function WorkspaceMembersBar({
  workspaceId,
  isOwner,
  refreshKey,
  onRefresh,
}: {
  workspaceId: number
  isOwner: boolean
  refreshKey: number
  onRefresh: () => void
}) {
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [loading, setLoading] = useState(true)

  // Add dialog
  const [addOpen, setAddOpen] = useState(false)
  const [searchResults, setSearchResults] = useState<{ id: number; username: string; display_name?: string }[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set())
  const [adding, setAdding] = useState(false)

  // Remove confirm
  const [removeTarget, setRemoveTarget] = useState<WorkspaceMember | null>(null)
  const [removing, setRemoving] = useState(false)

  useEffect(() => {
    fetchWorkspaceMembers(workspaceId)
      .then(setMembers)
      .catch(() => setMembers([]))
      .finally(() => setLoading(false))
  }, [workspaceId, refreshKey])

  const openAddDialog = () => {
    setAddOpen(true)
    setSearchQuery("")
    setSearchResults([])
    setSearched(false)
    setSelectedUserIds(new Set())
    setAdding(false)
  }

  const handleSearch = async () => {
    const q = searchQuery.trim()
    if (!q) return
    setSearching(true)
    setSearched(true)
    try {
      const res = await authFetch(`/api/v1/usermgr/users?page_size=50&search=${encodeURIComponent(q)}`)
      if (res.ok) {
        const data = await res.json()
        setSearchResults(
          (data.items ?? []).map((u: { id: number; username: string; first_name?: string; last_name?: string }) => ({
            id: u.id,
            username: u.username,
            display_name: [u.first_name, u.last_name].filter(Boolean).join(" ") || u.username,
          })),
        )
      }
    } catch { /* ignore */ }
    setSearching(false)
  }

  const toggleUser = (userId: number) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev)
      if (next.has(userId)) next.delete(userId)
      else next.add(userId)
      return next
    })
  }

  const handleAdd = async () => {
    if (selectedUserIds.size === 0) return
    setAdding(true)
    try {
      await bulkAddWorkspaceMembers(workspaceId, Array.from(selectedUserIds))
      setAddOpen(false)
      const updated = await fetchWorkspaceMembers(workspaceId)
      setMembers(updated)
      onRefresh()
    } catch { /* ignore */ }
    setAdding(false)
  }

  const handleRemove = async () => {
    if (!removeTarget) return
    setRemoving(true)
    try {
      await removeWorkspaceMember(workspaceId, removeTarget.id)
      setMembers((prev) => prev.filter((m) => m.id !== removeTarget.id))
      onRefresh()
    } catch { /* ignore */ }
    setRemoving(false)
    setRemoveTarget(null)
  }

  const memberIds = new Set(members.map((m) => m.user_id))
  const filteredUsers = searchResults.filter((u) => !memberIds.has(u.id))

  return (
    <>
      <Card>
        <CardHeader className="py-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Members ({members.length})</CardTitle>
            {isOwner && (
              <Button variant="outline" size="sm" className="text-xs" onClick={openAddDialog}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Add Member
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : members.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No members.</p>
          ) : (
            <div className="flex flex-wrap gap-3">
              {members.map((m) => (
                <div key={m.id} className="group relative flex flex-col items-center gap-1 w-20">
                  {isOwner && !m.is_owner && (
                    <button
                      className="absolute -top-1 -right-1 hidden group-hover:flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white text-[10px] leading-none hover:bg-red-600 z-10"
                      onClick={() => setRemoveTarget(m)}
                    >
                      ✕
                    </button>
                  )}
                  <Avatar className="h-9 w-9">
                    <AvatarFallback className="text-sm">{memberInitials(m)}</AvatarFallback>
                  </Avatar>
                  <span className="truncate text-sm text-center w-full">
                    {m.display_name || m.username}
                  </span>
                  {m.is_owner && (
                    <Badge variant="secondary" className="text-xs px-1.5 py-0">Owner</Badge>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Member Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Add Member</DialogTitle>
            <DialogDescription>Search for users by username or name and press Enter.</DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Enter username and press Enter..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSearch() }}
          />
          <div className="max-h-48 overflow-y-auto space-y-1 rounded-md border p-2">
            {searching ? (
              <div className="flex items-center justify-center gap-2 py-4">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Searching...</span>
              </div>
            ) : !searched ? (
              <p className="text-xs text-muted-foreground text-center py-4">Type a username and press Enter to search.</p>
            ) : filteredUsers.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-2">No users found.</p>
            ) : (
              filteredUsers.map((u) => (
                <label
                  key={u.id}
                  className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-muted/50 cursor-pointer"
                >
                  <Checkbox
                    checked={selectedUserIds.has(u.id)}
                    onCheckedChange={() => toggleUser(u.id)}
                  />
                  <span className="text-sm">{u.display_name || u.username}</span>
                  <span className="text-xs text-muted-foreground ml-auto">{u.username}</span>
                </label>
              ))
            )}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleAdd} disabled={adding || selectedUserIds.size === 0}>
              {adding && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Add ({selectedUserIds.size})
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Remove Confirm Dialog */}
      <Dialog open={!!removeTarget} onOpenChange={(open) => { if (!open) setRemoveTarget(null) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Remove Member</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove {removeTarget?.display_name || removeTarget?.username} from this workspace?
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setRemoveTarget(null)} disabled={removing}>Cancel</Button>
            <Button variant="destructive" size="sm" onClick={handleRemove} disabled={removing}>
              {removing && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Remove
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

interface DeployMappingEntry {
  service_key: string
  service_label: string
  icon: string
  pipeline_id: number | null
  pipeline_name: string | null
  constraint: string      // "per_workspace" | "per_user"
  constraint_label: string
}

// Map service_key to plugin_name patterns used in workspace services
const SERVICE_KEY_TO_PLUGIN: Record<string, string> = {
  // Development
  mlflow: "argus-mlflow",
  vscode: "argus-vscode-server",
  airflow: "argus-airflow",
  jupyter: "argus-jupyter",
  jupyter_tensorflow: "argus-jupyter-tensorflow",
  jupyter_pyspark: "argus-jupyter-pyspark",
  rstudio: "argus-rstudio",
  kserve: "argus-kserve",
  // Data
  neo4j: "argus-neo4j",
  milvus: "argus-milvus",
  mindsdb: "argus-mindsdb",
  trino: "argus-trino",
  starrocks: "argus-starrocks",
  kafka: "argus-kafka",
  nifi: "argus-nifi",
  postgresql: "argus-postgresql",
  mariadb: "argus-mariadb",
  // AutoML
  h2o: "argus-h2o",
  labelstudio: "argus-labelstudio",
  feast: "argus-feast",
  seldon: "argus-seldon",
  // AI Agent
  vllm: "argus-vllm",
  ollama: "argus-ollama",
  langserve: "argus-langserve",
  chromadb: "argus-chromadb",
  redis: "argus-redis",
}

function AddServiceButton({
  workspace,
  services,
  onDeployComplete,
}: {
  workspace: WorkspaceResponse
  services: WorkspaceService[]
  onDeployComplete: () => void
}) {
  const { user } = useAuth()
  const [menuItems, setMenuItems] = useState<DeployMappingEntry[]>([])

  // Confirm dialog state
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingItem, setPendingItem] = useState<DeployMappingEntry | null>(null)
  const [trinoTier, setTrinoTier] = useState<string>("development")
  const [starrocksTier, setStarrocksTier] = useState<string>("development")
  const [kafkaTier, setKafkaTier] = useState<string>("development")
  const [nifiTier, setNifiTier] = useState<string>("development")

  // Deploy progress dialog state
  const [deployOpen, setDeployOpen] = useState(false)
  const [deployLabel, setDeployLabel] = useState("")
  const [deployPhase, setDeployPhase] = useState<"progress" | "done" | "error">("progress")
  const [deployError, setDeployError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load deploy mappings
  useEffect(() => {
    authFetch("/api/v1/settings/deploy-mapping")
      .then((res) => (res.ok ? res.json() : { mappings: [] }))
      .then((data) => {
        // Only show services that have a pipeline mapped
        setMenuItems((data.mappings ?? []).filter((m: DeployMappingEntry) => m.pipeline_id))
      })
      .catch(() => setMenuItems([]))
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [])

  const handleMenuClick = (item: DeployMappingEntry) => {
    setPendingItem(item)
    setConfirmOpen(true)
  }

  const handleConfirmDeploy = async () => {
    if (!pendingItem) return
    const item = pendingItem
    setConfirmOpen(false)
    setPendingItem(null)

    setDeployLabel(item.service_label)
    setDeployPhase("progress")
    setDeployError(null)
    setDeployOpen(true)

    const pipelineId = item.pipeline_id
    if (!pipelineId) {
      setDeployError(`No pipeline mapped for "${item.service_label}". Configure it in Software Deployment > Pipeline To Deployment.`)
      setDeployPhase("error")
      return
    }

    // Build deploy payload — include plugin_config for tier selection
    const deployBody: Record<string, unknown> = { pipeline_id: pipelineId }
    if (item.service_key === "trino") {
      deployBody.plugin_config = { argus_trino_tier: trinoTier }
    } else if (item.service_key === "starrocks") {
      deployBody.plugin_config = { argus_starrocks_tier: starrocksTier }
    } else if (item.service_key === "kafka") {
      deployBody.plugin_config = { argus_kafka_tier: kafkaTier }
    } else if (item.service_key === "nifi") {
      deployBody.plugin_config = { argus_nifi_tier: nifiTier }
    }

    // Deploy
    try {
      const res = await authFetch(`/api/v1/workspace/workspaces/${workspace.id}/deploy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(deployBody),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Deploy failed: ${res.status}`)
      }
    } catch (e) {
      setDeployError(e instanceof Error ? e.message : "Deploy failed")
      setDeployPhase("error")
      return
    }

    // Poll audit logs for completion
    const pollStartedAt = new Date().toISOString()
    pollingRef.current = setInterval(async () => {
      try {
        const data = await fetchWorkspaceAuditLogs(workspace.id, 1, 50)
        const recent = data.items.filter((l) => l.created_at >= pollStartedAt)

        const completed = recent.find((l) =>
          l.action === "workflow_completed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        const failed = recent.find((l) =>
          l.action === "workflow_failed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        if (completed) {
          if (pollingRef.current) clearInterval(pollingRef.current)
          pollingRef.current = null
          setDeployPhase("done")
          onDeployComplete()
        } else if (failed) {
          if (pollingRef.current) clearInterval(pollingRef.current)
          pollingRef.current = null
          setDeployError(String((failed.detail as Record<string, unknown>)?.error || "Deployment failed"))
          setDeployPhase("error")
          onDeployComplete()
        }
      } catch { /* ignore */ }
    }, 2000)
  }

  const closeDeployDialog = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    setDeployOpen(false)
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="text-xs">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add Service
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {menuItems.length === 0 ? (
            <DropdownMenuItem disabled>
              <span className="text-muted-foreground text-xs">No services configured</span>
            </DropdownMenuItem>
          ) : (
            menuItems.map((item) => {
              const pluginName = SERVICE_KEY_TO_PLUGIN[item.service_key]
              const isProvisioning = workspace.status === "provisioning"

              // Check constraint
              let alreadyDeployed = false
              if (item.constraint === "per_workspace" && pluginName) {
                alreadyDeployed = services.some((s) => s.plugin_name === pluginName)
              } else if (item.constraint === "per_user" && pluginName && user) {
                // per_user: check if current user already has this service
                // (service metadata or username match)
                alreadyDeployed = services.some(
                  (s) => s.plugin_name === pluginName && s.username === user.username,
                )
              }

              return (
                <DropdownMenuItem
                  key={item.service_key}
                  onClick={() => !alreadyDeployed && handleMenuClick(item)}
                  disabled={isProvisioning || alreadyDeployed}
                >
                  <PluginIcon icon={item.icon} size={16} className="mr-2 rounded" />
                  {item.service_label}
                </DropdownMenuItem>
              )
            })
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Confirm Deploy Dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Deploy {pendingItem?.service_label}</DialogTitle>
            <DialogDescription>
              {pendingItem?.service_key === "trino" || pendingItem?.service_key === "starrocks" || pendingItem?.service_key === "kafka" || pendingItem?.service_key === "nifi"
                ? `Select a deployment tier for ${pendingItem?.service_label} and deploy to this workspace.`
                : `Would you like to deploy ${pendingItem?.service_label} to this workspace?`}
            </DialogDescription>
          </DialogHeader>

          {/* Trino Tier Selection */}
          {pendingItem?.service_key === "trino" && (
            <div className="space-y-2 py-2">
              {[
                { tier: "development", label: "Development", desc: "1 Coordinator (single node) — 1 CPU, 2 GiB", cpu: "1", mem: "2Gi" },
                { tier: "standard", label: "Standard", desc: "1 Coordinator + 1 Worker — 3 CPU, 6 GiB", cpu: "3", mem: "6Gi" },
                { tier: "performance", label: "Performance", desc: "2 Coordinators + 3 Workers — 8 CPU, 16 GiB", cpu: "8", mem: "16Gi" },
              ].map((t) => (
                <label
                  key={t.tier}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    trinoTier === t.tier ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                  }`}
                >
                  <input
                    type="radio"
                    name="trino-tier"
                    value={t.tier}
                    checked={trinoTier === t.tier}
                    onChange={() => setTrinoTier(t.tier)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-sm font-medium">{t.label}</div>
                    <div className="text-xs text-muted-foreground">{t.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          )}

          {/* StarRocks Tier Selection */}
          {pendingItem?.service_key === "starrocks" && (
            <div className="space-y-2 py-2">
              {[
                { tier: "development", label: "Development", desc: "1 FE + 1 BE — 3 CPU, 6 GiB" },
                { tier: "standard", label: "Standard", desc: "1 FE + 3 BE — 8 CPU, 16 GiB" },
                { tier: "performance", label: "Performance", desc: "1 FE + 5 BE — 12 CPU, 44 GiB" },
              ].map((t) => (
                <label
                  key={t.tier}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    starrocksTier === t.tier ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                  }`}
                >
                  <input
                    type="radio"
                    name="starrocks-tier"
                    value={t.tier}
                    checked={starrocksTier === t.tier}
                    onChange={() => setStarrocksTier(t.tier)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-sm font-medium">{t.label}</div>
                    <div className="text-xs text-muted-foreground">{t.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          )}

          {/* Kafka Tier Selection */}
          {pendingItem?.service_key === "kafka" && (
            <div className="space-y-2 py-2">
              {[
                { tier: "development", label: "Development", desc: "1 Combined Node — 1 CPU, 2 GiB" },
                { tier: "standard", label: "Standard", desc: "3 Combined Nodes — 3 CPU, 6 GiB" },
                { tier: "performance", label: "Performance", desc: "3 Nodes (high resources) — 6 CPU, 12 GiB" },
              ].map((t) => (
                <label
                  key={t.tier}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    kafkaTier === t.tier ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                  }`}
                >
                  <input
                    type="radio"
                    name="kafka-tier"
                    value={t.tier}
                    checked={kafkaTier === t.tier}
                    onChange={() => setKafkaTier(t.tier)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-sm font-medium">{t.label}</div>
                    <div className="text-xs text-muted-foreground">{t.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          )}

          {/* NiFi Tier Selection */}
          {pendingItem?.service_key === "nifi" && (
            <div className="space-y-2 py-2">
              {[
                { tier: "development", label: "Development", desc: "1 NiFi + Registry — 3 CPU, 3 GiB" },
                { tier: "standard", label: "Standard", desc: "3 NiFi (cluster) + Registry — 13 CPU, 13 GiB" },
                { tier: "performance", label: "Performance", desc: "3 NiFi (high) + Registry — 25 CPU, 25 GiB" },
              ].map((t) => (
                <label
                  key={t.tier}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    nifiTier === t.tier ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                  }`}
                >
                  <input
                    type="radio"
                    name="nifi-tier"
                    value={t.tier}
                    checked={nifiTier === t.tier}
                    onChange={() => setNifiTier(t.tier)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-sm font-medium">{t.label}</div>
                    <div className="text-xs text-muted-foreground">{t.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleConfirmDeploy}>
              Deploy
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Deploy Progress Dialog */}
      <Dialog open={deployOpen} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-sm [&>button]:hidden" onPointerDownOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle>
              {deployPhase === "progress" && `Deploying ${deployLabel}`}
              {deployPhase === "done" && `${deployLabel} Deployed`}
              {deployPhase === "error" && `${deployLabel} Deployment`}
            </DialogTitle>
          </DialogHeader>

          <div className="py-4">
            {deployPhase === "progress" && (
              <div className="flex flex-col items-center gap-3 py-4">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Please wait a moment...</p>
              </div>
            )}
            {deployPhase === "done" && (
              <div className="rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-2 text-sm dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800">
                Service has been deployed successfully.
              </div>
            )}
            {deployPhase === "error" && deployError && (
              <div className="rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm dark:bg-red-950 dark:text-red-200 dark:border-red-800">
                {deployError}
              </div>
            )}
          </div>

          {deployPhase !== "progress" && (
            <div className="flex justify-center">
              <Button size="sm" onClick={closeDeployDialog}>Close</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  Workspace Resource Dashboard                                       */
/* ------------------------------------------------------------------ */

function WorkspaceResourceView({ workspaceId }: { workspaceId: number }) {
  const { user } = useAuth()
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null)
  const [services, setServices] = useState<WorkspaceService[]>([])
  const [gitlabServerUrl, setGitlabServerUrl] = useState<string>("")
  const [perUserPlugins, setPerUserPlugins] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  const handleDeployComplete = useCallback(() => {
    setRefreshKey((k) => k + 1)
  }, [])

  const handleDeleteService = useCallback(async (svc: WorkspaceService) => {
    await deleteWorkspaceService(workspaceId, svc.id)
    setRefreshKey((k) => k + 1)
  }, [workspaceId])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [ws, svc, gitlabRes, cfgRes, mappingRes] = await Promise.all([
          fetchWorkspace(workspaceId),
          fetchWorkspaceServices(workspaceId),
          authFetch("/api/v1/settings/gitlab").catch(() => null),
          authFetch("/api/v1/settings/configuration").catch(() => null),
          authFetch("/api/v1/settings/deploy-mapping").catch(() => null),
        ])
        if (!cancelled) {
          setWorkspace(ws)
          setServices(svc)
          // Try /settings/gitlab first, fall back to /settings/configuration
          let glUrl = ""
          if (gitlabRes?.ok) {
            const data = await gitlabRes.json()
            glUrl = data.url || ""
          }
          if (!glUrl && cfgRes?.ok) {
            const data = await cfgRes.json()
            const gitlabCat = data.categories?.find(
              (c: { category: string }) => c.category === "gitlab",
            )
            glUrl = gitlabCat?.items?.gitlab_url || ""
          }
          if (glUrl) setGitlabServerUrl(glUrl.replace(/\/+$/, ""))

          // Build set of per_user plugin names
          if (mappingRes?.ok) {
            const mData = await mappingRes.json()
            const perUser = new Set<string>()
            for (const m of mData.mappings ?? []) {
              if (m.constraint === "per_user") {
                const pluginName = SERVICE_KEY_TO_PLUGIN[m.service_key as string]
                if (pluginName) perUser.add(pluginName)
              }
            }
            setPerUserPlugins(perUser)
          }
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [workspaceId, refreshKey])

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!workspace) {
    return (
      <div className="flex flex-1 items-center justify-center py-20 text-muted-foreground">
        Workspace not found.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="flex items-center gap-4">
        <div>
          <h2 className="text-lg font-semibold">{workspace.display_name}</h2>
          <p className="text-sm text-muted-foreground">
            <span className="font-mono">{workspace.name}</span>
            <span className="mx-2 text-muted-foreground/50">|</span>
            <span>{formatDateTime(workspace.created_at)}</span>
          </p>
        </div>
        <div className="ml-auto">{statusBadge(workspace.status)}</div>
      </div>

      {/* Dashboard: overview cards, service health, storage, activity */}
      {(workspace.status === "active" || workspace.status === "failed") && (
        <WorkspaceDashboardPanel workspaceId={workspace.id} />
      )}


      {(() => {
        // Categorize services
        const hiddenPlugins = new Set(["argus-minio-workspace", "argus-minio-setup"])
        const defaultPlugins = new Set(["argus-gitlab"])
        const all = services.filter((s) => !hiddenPlugins.has(s.plugin_name))

        // Default services (GitLab etc.) — always present for every workspace
        const defaultServices = all
          .filter((s) => defaultPlugins.has(s.plugin_name))
          .map((svc) => {
            if (svc.plugin_name !== "argus-gitlab") return svc

            // Reconstruct GitLab URL from Settings server URL + project path
            const rawUrl = workspace.gitlab_project_url || svc.endpoint
            let endpoint = rawUrl || ""
            if (gitlabServerUrl && rawUrl) {
              try {
                const parsed = new URL(rawUrl)
                endpoint = `${gitlabServerUrl}${parsed.pathname}`
              } catch { /* use rawUrl */ }
            }

            // Use user's GitLab credentials instead of service-level ones
            return {
              ...svc,
              endpoint,
              username: user?.gitlab_username || svc.username,
              password: user?.gitlab_password || null,
              // Custom display labels for expanded detail
              _usernameLabel: "Gitlab Username",
              _passwordLabel: "Gitlab Password",
              _hideUrl: true,
            } as WorkspaceService & { _usernameLabel?: string; _passwordLabel?: string; _hideUrl?: boolean }
          })

        // Deployed services (everything except hidden + default)
        // For per_user services, only show current user's instances
        const deployed = all
          .filter((s) => {
            if (defaultPlugins.has(s.plugin_name)) return false
            if (perUserPlugins.has(s.plugin_name) && user) {
              return s.username === user.username
            }
            return true
          })
          .map((svc) => {
            if (svc.plugin_name === "argus-mariadb" || svc.plugin_name === "argus-postgresql") {
              return {
                ...svc,
                username: null,
                password: null,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name === "argus-mlflow" || svc.plugin_name === "argus-airflow") {
              return {
                ...svc,
                username: svc.plugin_name === "argus-mlflow" ? null : svc.username,
                metadata: { ...svc.metadata, display: {} },
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name === "argus-vscode-server") {
              return {
                ...svc,
                username: null,
                metadata: {
                  ...svc.metadata,
                  display: {
                    "Workspace Bucket": "/workspace",
                    "User Bucket": "/data",
                  },
                },
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name.startsWith("argus-jupyter")) {
              return {
                ...svc,
                username: null,
                metadata: {
                  ...svc.metadata,
                  display: {
                    "Workspace": "/workspace (Workspace Bucket)",
                    "User": "/data (User Bucket)",
                  },
                },
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name === "argus-rstudio") {
              return {
                ...svc,
                username: null,
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name === "argus-labelstudio") {
              return {
                ...svc,
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name === "argus-redis") {
              const meta = svc.metadata ?? {}
              const internal = (meta.internal ?? {}) as Record<string, unknown>
              const display = (meta.display ?? {}) as Record<string, unknown>
              // Derive hostname/port from internal metadata or endpoint
              const hostname = internal.hostname
                || svc.endpoint?.replace(/^https?:\/\//, "").replace(/:\d+$/, "")
                || ""
              const port = internal.port || "6379"
              return {
                ...svc,
                endpoint: null,
                username: null,
                password: null,
                metadata: {
                  ...meta,
                  display: {
                    "Hostname": hostname,
                    "Port": String(port),
                    "Storage": display.Storage || display.storage_size || "",
                    "Max Memory": display["Max Memory"] || display.maxmemory || "",
                  },
                },
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            return svc
          })

        return (
          <>
            {/* Members */}
            <WorkspaceMembersBar
              workspaceId={workspace.id}
              isOwner={!!user && String(workspace.created_by) === user.sub}
              refreshKey={refreshKey}
              onRefresh={handleDeployComplete}
            />

            {/* Default Services */}
            {defaultServices.length > 0 && (
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-sm">
                    Default Services ({defaultServices.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4 pt-0">
                  <ServiceDataList services={defaultServices} hideTimestamps workspaceName={workspace.name} />
                </CardContent>
              </Card>
            )}

            {/* Deployed Services */}
            <Card>
              <CardHeader className="py-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">
                    Deployed Services ({deployed.length})
                  </CardTitle>
                  <AddServiceButton
                    workspace={workspace}
                    services={services}
                    onDeployComplete={handleDeployComplete}
                  />
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-4 pt-0">
                {deployed.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground text-sm">
                    No services deployed yet. Click "Add Service" to deploy one.
                  </div>
                ) : (
                  <ServiceDataList
                    services={deployed}
                    onDelete={handleDeleteService}
                    isOwner={!!user && String(workspace.created_by) === user.sub}
                    perUserPlugins={perUserPlugins}
                    workspaceId={workspace.id}
                    workspaceName={workspace.name}
                  />
                )}
              </CardContent>
            </Card>
          </>
        )
      })()}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main component: switches between list and resource view            */
/* ------------------------------------------------------------------ */

const WS_SESSION_KEY = "argus_last_workspace_id"

export function WorkspaceOverview() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const wsId = searchParams.get("ws")
  const [checked, setChecked] = useState(false)

  // If ws param present, remember it
  useEffect(() => {
    if (wsId) {
      sessionStorage.setItem(WS_SESSION_KEY, wsId)
      setChecked(true)
    }
  }, [wsId])

  // If no ws param, try last selected or first available
  useEffect(() => {
    if (wsId) return

    // Try last selected workspace from session
    const lastId = sessionStorage.getItem(WS_SESSION_KEY)
    if (lastId) {
      router.replace(`/dashboard/workspace?ws=${lastId}`)
      return
    }

    // No last selection — fetch and pick first
    authFetch("/api/v1/workspace/workspaces/my")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: MyWorkspace[]) => {
        if (data.length > 0) {
          router.replace(`/dashboard/workspace?ws=${data[0].id}`)
        } else {
          setChecked(true)
        }
      })
      .catch(() => setChecked(true))
  }, [wsId, router])

  if (!checked) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (wsId) {
    return <WorkspaceResourceView workspaceId={Number(wsId)} />
  }

  return <NoWorkspaceView />
}
