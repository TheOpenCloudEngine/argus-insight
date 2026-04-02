"use client"

import { useEffect, useState } from "react"
import {
  Activity,
  CheckCircle2,
  Clock,
  Container,
  HardDrive,
  Loader2,
  RotateCcw,
  Server,
  XCircle,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"

import {
  fetchWorkspaceDashboard,
  fetchWorkspaceResourceUsage,
} from "@/features/workspaces/api"
import type {
  ActivityItem,
  ServiceHealthItem,
  StorageItem,
  WorkspaceDashboard,
  WorkspaceResourceUsage,
} from "@/features/workspaces/types"

// ── Helpers ───────────────────────────────────────────────

function formatUptime(seconds: number | null): string {
  if (seconds == null) return "—"
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return `${Math.floor(days / 30)}mo ago`
}

function actionIcon(action: string) {
  if (action.includes("created") || action.includes("deploy") || action.includes("completed"))
    return <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
  if (action.includes("failed") || action.includes("error"))
    return <XCircle className="h-3.5 w-3.5 text-red-500" />
  if (action.includes("member"))
    return <Activity className="h-3.5 w-3.5 text-blue-500" />
  return <Clock className="h-3.5 w-3.5 text-muted-foreground" />
}

function parseCapacity(s: string | null): number | null {
  if (!s) return null
  const m = s.match(/^(\d+(?:\.\d+)?)\s*(Gi|Mi|Ti|Ki|G|M|T|K)?$/i)
  if (!m) return null
  const val = parseFloat(m[1])
  const unit = (m[2] || "").toLowerCase()
  if (unit === "ti") return val * 1024
  if (unit === "gi" || unit === "g") return val
  if (unit === "mi" || unit === "m") return val / 1024
  if (unit === "ki" || unit === "k") return val / (1024 * 1024)
  return val
}

// ── Overview Cards ────────────────────────────────────────

function OverviewCards({
  dashboard,
  resourceUsage,
}: {
  dashboard: WorkspaceDashboard
  resourceUsage: WorkspaceResourceUsage | null
}) {
  const totalStorageGi = dashboard.storage.reduce((sum, s) => sum + (parseCapacity(s.capacity) ?? 0), 0)

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {/* Services */}
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <div className="rounded-lg bg-blue-100 p-2 dark:bg-blue-900">
            <Container className="h-5 w-5 text-blue-600 dark:text-blue-300" />
          </div>
          <div>
            <p className="text-2xl font-bold">{dashboard.running_services}<span className="text-sm font-normal text-muted-foreground">/{dashboard.total_services}</span></p>
            <p className="text-xs text-muted-foreground">Services Running</p>
          </div>
        </CardContent>
      </Card>

      {/* CPU */}
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <div className="rounded-lg bg-green-100 p-2 dark:bg-green-900">
            <Activity className="h-5 w-5 text-green-600 dark:text-green-300" />
          </div>
          <div className="flex-1">
            <p className="text-2xl font-bold">
              {resourceUsage ? `${resourceUsage.cpu_used.toFixed(1)}` : "—"}
              <span className="text-sm font-normal text-muted-foreground">
                {resourceUsage?.cpu_limit ? ` / ${resourceUsage.cpu_limit}` : ""} cores
              </span>
            </p>
            <p className="text-xs text-muted-foreground">CPU Used</p>
            {resourceUsage?.cpu_limit && (
              <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-green-500"
                  style={{ width: `${Math.min((resourceUsage.cpu_used / resourceUsage.cpu_limit) * 100, 100)}%` }}
                />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Memory */}
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <div className="rounded-lg bg-purple-100 p-2 dark:bg-purple-900">
            <Server className="h-5 w-5 text-purple-600 dark:text-purple-300" />
          </div>
          <div className="flex-1">
            <p className="text-2xl font-bold">
              {resourceUsage ? `${resourceUsage.memory_used_gb.toFixed(1)}` : "—"}
              <span className="text-sm font-normal text-muted-foreground">
                {resourceUsage?.memory_limit_gb ? ` / ${resourceUsage.memory_limit_gb}` : ""} Gi
              </span>
            </p>
            <p className="text-xs text-muted-foreground">Memory Used</p>
            {resourceUsage?.memory_limit_gb && (
              <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-purple-500"
                  style={{ width: `${Math.min((resourceUsage.memory_used_gb / resourceUsage.memory_limit_gb) * 100, 100)}%` }}
                />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Storage */}
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <div className="rounded-lg bg-orange-100 p-2 dark:bg-orange-900">
            <HardDrive className="h-5 w-5 text-orange-600 dark:text-orange-300" />
          </div>
          <div>
            <p className="text-2xl font-bold">
              {totalStorageGi > 0 ? `${totalStorageGi.toFixed(0)}` : "—"}
              <span className="text-sm font-normal text-muted-foreground"> Gi</span>
            </p>
            <p className="text-xs text-muted-foreground">Storage ({dashboard.storage.length} PVCs)</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// ── Service Health Table ──────────────────────────────────

function ServiceHealthTable({ items }: { items: ServiceHealthItem[] }) {
  if (items.length === 0) return null

  return (
    <Card className="py-0">
      <CardContent className="p-0">
        <div className="max-h-[300px] overflow-auto rounded-[inherit]">
          <table className="w-full">
            <thead className="sticky top-0 z-10">
              <tr className="border-b bg-muted/30 text-sm text-muted-foreground">
                <th className="px-4 py-1 text-left font-medium">Service</th>
                <th className="px-4 py-1 text-left font-medium">Status</th>
                <th className="px-4 py-1 text-left font-medium">Pod</th>
                <th className="px-4 py-1 text-right font-medium">CPU</th>
                <th className="px-4 py-1 text-right font-medium">Memory</th>
                <th className="px-4 py-1 text-right font-medium">Restarts</th>
                <th className="px-4 py-1 text-right font-medium">Uptime</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {items.map((h) => (
                <tr key={h.pod_name} className="border-b last:border-b-0">
                  <td className="px-4 py-1 font-medium">
                    {h.display_name || h.plugin_name}
                  </td>
                  <td className="px-4 py-1">
                    {h.ready ? (
                      <Badge className="bg-green-100 text-green-800 text-[10px] dark:bg-green-900 dark:text-green-200">
                        <CheckCircle2 className="mr-1 h-3 w-3" />Running
                      </Badge>
                    ) : (
                      <Badge className="bg-yellow-100 text-yellow-800 text-[10px] dark:bg-yellow-900 dark:text-yellow-200">
                        <Clock className="mr-1 h-3 w-3" />{h.phase}
                      </Badge>
                    )}
                  </td>
                  <td className="px-4 py-1 font-mono text-muted-foreground">{h.pod_name}</td>
                  <td className="px-4 py-1 text-right">
                    {h.cpu_request && <span>{h.cpu_request}{h.cpu_limit && ` / ${h.cpu_limit}`}</span>}
                  </td>
                  <td className="px-4 py-1 text-right">
                    {h.memory_request && <span>{h.memory_request}{h.memory_limit && ` / ${h.memory_limit}`}</span>}
                  </td>
                  <td className="px-4 py-1 text-right">
                    {h.restarts > 0 ? (
                      <span className="inline-flex items-center gap-1 text-orange-600">
                        <RotateCcw className="h-3 w-3" />{h.restarts}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">0</span>
                    )}
                  </td>
                  <td className="px-4 py-1 text-right text-muted-foreground">
                    {formatUptime(h.uptime_seconds)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Storage Usage ─────────────────────────────────────────

function StorageUsage({ items }: { items: StorageItem[] }) {
  if (items.length === 0) return null

  return (
    <Card className="flex flex-col">
      <CardHeader className="shrink-0 py-3">
        <CardTitle className="text-sm">Storage (PVCs)</CardTitle>
      </CardHeader>
      <CardContent className="max-h-[200px] overflow-y-auto space-y-2 pt-0 text-sm">
        {items.map((s) => {
          const gi = parseCapacity(s.capacity)
          return (
            <div key={s.name} className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="font-mono">{s.name}</span>
                {s.service_hint && (
                  <span className="ml-2 text-muted-foreground">({s.service_hint})</span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge variant={s.phase === "Bound" ? "secondary" : "outline"} className="text-[10px]">
                  {s.phase}
                </Badge>
                <span className="font-medium w-16 text-right">
                  {gi != null ? `${gi}Gi` : s.capacity ?? "—"}
                </span>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

// ── Recent Activity ───────────────────────────────────────

function RecentActivity({ items }: { items: ActivityItem[] }) {
  if (items.length === 0) return null

  return (
    <Card className="flex flex-col">
      <CardHeader className="shrink-0 py-3">
        <CardTitle className="text-sm">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent className="max-h-[200px] overflow-y-auto space-y-0 pt-0 text-sm">
        {items.map((a, i) => {
          const detailText = a.detail && Object.keys(a.detail).length > 0
            ? Object.entries(a.detail).map(([k, v]) => `${k}: ${v}`).join(", ")
            : null
          return (
            <div key={i} className="flex items-start gap-3 py-2 border-b last:border-b-0">
              <div className="mt-0.5 shrink-0">{actionIcon(a.action)}</div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{a.action.replace(/_/g, " ")}</span>
                  {a.actor_username && (
                    <span className="text-muted-foreground">by {a.actor_username}</span>
                  )}
                </div>
                {detailText && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <p className="text-muted-foreground mt-0.5 truncate cursor-default">
                        {detailText}
                      </p>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-[500px] whitespace-pre-wrap text-xs">
                      {detailText}
                    </TooltipContent>
                  </Tooltip>
                )}
              </div>
              <span className="text-xs text-muted-foreground shrink-0">
                {timeAgo(a.created_at)}
              </span>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

// ── Main Export ────────────────────────────────────────────

interface WorkspaceDashboardPanelProps {
  workspaceId: number
}

export function WorkspaceDashboardPanel({
  workspaceId,
}: WorkspaceDashboardPanelProps) {
  const [dashboard, setDashboard] = useState<WorkspaceDashboard | null>(null)
  const [resourceUsage, setResourceUsage] = useState<WorkspaceResourceUsage | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.all([
      fetchWorkspaceDashboard(workspaceId),
      fetchWorkspaceResourceUsage(workspaceId).catch(() => null),
    ])
      .then(([db, ru]) => {
        setDashboard(db)
        setResourceUsage(ru)
      })
      .catch((e) => console.error("Failed to load dashboard:", e))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [workspaceId])

  if (loading && !dashboard) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!dashboard) return null

  return (
    <div className="space-y-4">
      {/* Overview cards */}
      <OverviewCards dashboard={dashboard} resourceUsage={resourceUsage} />

      {/* Service Health */}
      <ServiceHealthTable items={dashboard.service_health} />

      {/* Bottom grid: Storage + Activity */}
      <div className="grid gap-4 lg:grid-cols-2">
        <StorageUsage items={dashboard.storage} />
        <RecentActivity items={dashboard.recent_activity} />
      </div>
    </div>
  )
}
