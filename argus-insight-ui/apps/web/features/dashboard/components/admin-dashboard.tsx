"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  AlertCircle,
  Briefcase,
  CheckCircle2,
  Clock,
  Container,
  HardDrive,
  Loader2,
  MessageSquareMore,
  Server,
  Users,
  XCircle,
} from "lucide-react"
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Badge } from "@workspace/ui/components/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"

import { fetchAdminDashboard } from "@/features/dashboard/api"
import type { AdminDashboard } from "@/features/dashboard/types"

// ── Colors ────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  open: "#3b82f6",
  in_progress: "#f59e0b",
  resolved: "#22c55e",
  rejected: "#9ca3af",
  closed: "#6b7280",
}

const CATEGORY_COLORS: Record<string, string> = {
  resource_request: "#f59e0b",
  service_issue: "#ef4444",
  feature_request: "#3b82f6",
  account: "#8b5cf6",
  general: "#6b7280",
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#3b82f6",
  low: "#9ca3af",
}

const WS_BAR_COLORS = ["#3b82f6", "#8b5cf6", "#f59e0b", "#22c55e", "#ef4444", "#06b6d4", "#ec4899", "#14b8a6"]

const CATEGORY_LABELS: Record<string, string> = {
  resource_request: "Resource",
  service_issue: "Service",
  feature_request: "Feature",
  account: "Account",
  general: "General",
}

// ── Helpers ───────────────────────────────────────────────

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return "just now"
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h`
  const d = Math.floor(h / 24)
  return `${d}d`
}

// ── Summary Cards ─────────────────────────────────────────

function SummaryCards({ data }: { data: AdminDashboard }) {
  const cards = [
    {
      label: "Workspaces",
      value: data.workspaces_active,
      sub: `${data.workspaces_total} total`,
      icon: Briefcase,
      color: "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300",
    },
    {
      label: "Users",
      value: data.users_active,
      sub: `${data.users_total} total`,
      icon: Users,
      color: "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300",
    },
    {
      label: "Services",
      value: data.services_running,
      sub: `${data.services_total} total`,
      icon: Container,
      color: "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300",
    },
    {
      label: "VOC Open",
      value: data.voc_open,
      sub: data.voc_critical > 0 ? `${data.voc_critical} critical` : "0 critical",
      icon: MessageSquareMore,
      color: data.voc_critical > 0
        ? "bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-300"
        : "bg-orange-100 text-orange-600 dark:bg-orange-900 dark:text-orange-300",
    },
  ]

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardContent className="flex items-center gap-3 p-4">
            <div className={`rounded-lg p-2 ${c.color}`}>
              <c.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">
                {c.value}
                <span className="text-sm font-normal text-muted-foreground ml-1">{c.sub}</span>
              </p>
              <p className="text-xs text-muted-foreground">{c.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// ── Cluster Resource Gauges ───────────────────────────────

function ResourceGauge({
  label,
  used,
  limit,
  unit,
  color,
}: {
  label: string
  used: number
  limit: number
  unit: string
  color: string
}) {
  const hasLimit = limit > 0
  const pct = hasLimit ? Math.min((used / limit) * 100, 100) : 0
  const r = 45
  const circ = 2 * Math.PI * r
  const offset = circ - (pct / 100) * circ

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-[110px] w-[110px]">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle
            cx="50" cy="50" r={r}
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth="8"
          />
          {pct > 0 && (
            <circle
              cx="50" cy="50" r={r}
              fill="none"
              stroke={color}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circ}
              strokeDashoffset={offset}
              className="transition-[stroke-dashoffset] duration-500"
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {hasLimit ? (
            <span className="text-lg font-bold">{pct.toFixed(0)}%</span>
          ) : (
            <span className="text-lg font-bold">{used > 0 ? used.toFixed(1) : "—"}</span>
          )}
        </div>
      </div>
      <p className="text-sm text-muted-foreground mt-1">
        {hasLimit ? `${used}${unit} / ${limit}${unit}` : `${used}${unit}`}
      </p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}

function ClusterResources({ data }: { data: AdminDashboard }) {
  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-sm">Cluster Resources (Requests / Limits)</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-around items-end py-2">
        <ResourceGauge
          label="CPU"
          used={data.cluster_cpu_used}
          limit={data.cluster_cpu_limit}
          unit=" cores"
          color="#22c55e"
        />
        <ResourceGauge
          label="Memory"
          used={data.cluster_memory_used_gb}
          limit={data.cluster_memory_limit_gb}
          unit=" Gi"
          color="#8b5cf6"
        />
        {/* Storage: total only, no ratio gauge */}
        <div className="flex flex-col items-center">
          <div className="flex h-[110px] w-[110px] items-center justify-center rounded-full border-8 border-muted">
            <div className="text-center">
              <span className="text-lg font-bold">
                {data.cluster_storage_gb > 0 ? data.cluster_storage_gb.toFixed(0) : "—"}
              </span>
              <span className="text-xs text-muted-foreground"> Gi</span>
            </div>
          </div>
          <p className="text-sm text-muted-foreground mt-1">Total Provisioned</p>
          <p className="text-xs text-muted-foreground">Storage</p>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Workspace Overview ────────────────────────────────────

function WorkspaceOverviewChart({ data }: { data: AdminDashboard }) {
  const stats = data.workspace_stats
  if (stats.length === 0) return null

  // Donut chart for status
  const statusCounts: Record<string, number> = {}
  for (const ws of stats) {
    statusCounts[ws.status] = (statusCounts[ws.status] || 0) + 1
  }
  const donutData = Object.entries(statusCounts).map(([name, value]) => ({ name, value }))
  const WS_STATUS_COLORS: Record<string, string> = {
    active: "#22c55e",
    provisioning: "#3b82f6",
    failed: "#ef4444",
  }

  return (
    <Card className="flex flex-col">
      <CardHeader className="shrink-0 py-3">
        <CardTitle className="text-sm">Workspace Overview</CardTitle>
      </CardHeader>
      <CardContent className="max-h-[280px] overflow-y-auto pt-0">
        <div className="flex gap-4">
          {/* Donut */}
          <div className="shrink-0">
            <ResponsiveContainer width={100} height={100}>
              <PieChart>
                <Pie data={donutData} dataKey="value" cx="50%" cy="50%" innerRadius={28} outerRadius={45} strokeWidth={0}>
                  {donutData.map((d) => (
                    <Cell key={d.name} fill={WS_STATUS_COLORS[d.name] || "#6b7280"} />
                  ))}
                </Pie>
                <RechartsTooltip formatter={(v: number, name: string) => [v, name]} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 text-[10px] text-muted-foreground">
              {donutData.map((d) => (
                <span key={d.name} className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full" style={{ background: WS_STATUS_COLORS[d.name] || "#6b7280" }} />
                  {d.name} ({d.value})
                </span>
              ))}
            </div>
          </div>
          {/* Table */}
          <div className="flex-1 text-sm">
            <table className="w-full">
              <thead className="sticky top-0">
                <tr className="text-xs text-muted-foreground border-b bg-background">
                  <th className="text-left py-1 font-medium">Workspace</th>
                  <th className="text-right py-1 font-medium">Svc</th>
                  <th className="text-right py-1 font-medium">CPU</th>
                  <th className="text-right py-1 font-medium">Mem</th>
                </tr>
              </thead>
              <tbody>
                {stats.map((ws) => (
                  <tr key={ws.id} className="border-b last:border-b-0">
                    <td className="py-1">{ws.display_name}</td>
                    <td className="py-1 text-right">{ws.service_count}</td>
                    <td className="py-1 text-right">{ws.cpu_used}</td>
                    <td className="py-1 text-right">{ws.memory_used_gb}Gi</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── VOC Status Chart ──────────────────────────────────────

function VocStatusChart({ data }: { data: AdminDashboard }) {
  const statusData = Object.entries(data.voc_by_status).map(([name, value]) => ({ name, value }))
  const categoryData = Object.entries(data.voc_by_category).map(([name, value]) => ({
    name: CATEGORY_LABELS[name] || name,
    value,
    key: name,
  }))

  return (
    <Card className="flex flex-col">
      <CardHeader className="shrink-0 py-3">
        <CardTitle className="text-sm">
          VOC Distribution
          <span className="ml-2 font-normal text-muted-foreground">
            {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long" })}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 pt-0 space-y-3">
        {/* By status - horizontal bars */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">By Status</p>
          <ResponsiveContainer width="100%" height={statusData.length * 24 + 10}>
            <BarChart data={statusData} layout="vertical" margin={{ left: 70, right: 10, top: 0, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={65} />
              <RechartsTooltip />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={14}>
                {statusData.map((d) => (
                  <Cell key={d.name} fill={STATUS_COLORS[d.name] || "#6b7280"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        {/* By category */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">By Category</p>
          <ResponsiveContainer width="100%" height={categoryData.length * 24 + 10}>
            <BarChart data={categoryData} layout="vertical" margin={{ left: 70, right: 10, top: 0, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={65} />
              <RechartsTooltip />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={14}>
                {categoryData.map((d) => (
                  <Cell key={d.key} fill={CATEGORY_COLORS[d.key] || "#6b7280"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Recent VOC ────────────────────────────────────────────

function RecentVocPanel({ data }: { data: AdminDashboard }) {
  const router = useRouter()
  const priBadge = (pri: string) => {
    const colors: Record<string, string> = {
      critical: "bg-red-100 text-red-800",
      high: "bg-orange-100 text-orange-800",
      medium: "bg-blue-50 text-blue-700",
      low: "bg-gray-100 text-gray-600",
    }
    return <Badge className={`text-[10px] ${colors[pri] || ""}`}>{pri}</Badge>
  }

  return (
    <Card className="flex flex-col">
      <CardHeader className="shrink-0 py-3">
        <CardTitle className="text-sm">Recent VOC Issues</CardTitle>
      </CardHeader>
      <CardContent className="max-h-[200px] overflow-y-auto pt-0 text-sm">
        {data.recent_voc.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">No VOC issues.</p>
        ) : (
          data.recent_voc.map((v) => (
            <div
              key={v.id}
              className="flex items-center gap-2 py-1.5 border-b last:border-b-0 cursor-pointer hover:bg-muted/50 rounded px-1"
              onClick={() => router.push(`/dashboard/voc/${v.id}`)}
            >
              <span className="font-mono text-xs text-muted-foreground w-6">#{v.id}</span>
              {priBadge(v.priority)}
              <span className="flex-1 truncate">{v.title}</span>
              {v.workspace_name && (
                <span className="text-xs text-muted-foreground shrink-0">{v.workspace_name}</span>
              )}
              <span className="text-xs text-muted-foreground shrink-0">{timeAgo(v.created_at)}</span>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}

// ── Recent Activity ───────────────────────────────────────

function RecentActivityPanel({ data }: { data: AdminDashboard }) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="shrink-0 py-3">
        <CardTitle className="text-sm">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent className="max-h-[200px] overflow-y-auto pt-0 text-sm">
        {data.recent_activity.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">No recent activity.</p>
        ) : (
          data.recent_activity.map((a, i) => (
            <div key={i} className="flex items-center gap-2 py-1.5 border-b last:border-b-0">
              {a.action.includes("created") || a.action.includes("completed") ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
              ) : a.action.includes("failed") ? (
                <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />
              ) : (
                <Clock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              )}
              <span className="flex-1 truncate">
                {a.action.replace(/_/g, " ")}
                {a.workspace_name && <span className="text-muted-foreground"> · {a.workspace_name}</span>}
              </span>
              {a.actor_username && (
                <span className="text-xs text-muted-foreground shrink-0">{a.actor_username}</span>
              )}
              <span className="text-xs text-muted-foreground shrink-0">{timeAgo(a.created_at)}</span>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}

// ── Main Export ────────────────────────────────────────────

export function AdminDashboardView() {
  const [data, setData] = useState<AdminDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchAdminDashboard()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
        <AlertCircle className="mr-2 h-5 w-5" />
        {error || "Failed to load dashboard."}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Row 1: Summary cards */}
      <SummaryCards data={data} />

      {/* Row 2: Cluster resources */}
      <ClusterResources data={data} />

      {/* Row 3: Workspace + VOC */}
      <div className="grid gap-4 lg:grid-cols-2">
        <WorkspaceOverviewChart data={data} />
        <VocStatusChart data={data} />
      </div>

      {/* Row 4: Recent panels */}
      <div className="grid gap-4 lg:grid-cols-2">
        <RecentVocPanel data={data} />
        <RecentActivityPanel data={data} />
      </div>
    </div>
  )
}
