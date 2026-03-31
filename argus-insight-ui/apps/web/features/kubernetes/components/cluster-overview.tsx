"use client"

import { useMemo } from "react"
import {
  Box,
  Clock,
  Container,
  FolderOpen,
  HardDrive,
  Layers,
  Network,
  Server,
  XCircle,
  AlertTriangle,
} from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Badge } from "@workspace/ui/components/badge"
import { Separator } from "@workspace/ui/components/separator"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts"
import type {
  ClusterOverview as ClusterOverviewType,
  ResourceCount,
  K8sEvent,
  NodeResourceInfo,
} from "../types"
import { useClusterOverview } from "../hooks/use-k8s-resources"
import { formatAge } from "../lib/formatters"

export function ClusterOverview() {
  const { data, loading, error } = useClusterOverview()

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
        <XCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
        <p className="text-sm font-medium text-destructive">Cluster Connection Failed</p>
        <p className="text-sm text-muted-foreground mt-1">{error}</p>
      </div>
    )
  }

  if (loading || !data) {
    return <ClusterOverviewSkeleton />
  }

  if (!data.cluster.connected) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
        <XCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
        <p className="text-sm font-medium text-destructive">Cluster Not Connected</p>
        <p className="text-sm text-muted-foreground mt-1">{data.cluster.error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Cluster Info Bar */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
          <span className="font-medium">Connected</span>
        </div>
        <Separator orientation="vertical" className="h-4" />
        <span className="text-muted-foreground">
          Kubernetes {data.cluster.version}
        </span>
        {data.cluster.platform && (
          <>
            <Separator orientation="vertical" className="h-4" />
            <span className="text-muted-foreground">{data.cluster.platform}</span>
          </>
        )}
      </div>

      {/* Summary Cards - 6 cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <SummaryCard title="Nodes" icon={Server} count={data.nodes} color="text-blue-500" bg="bg-blue-500/10" />
        <SummaryCard title="Pods" icon={Container} count={data.pods} color="text-green-500" bg="bg-green-500/10" />
        <SummaryCard title="Deployments" icon={Layers} count={data.deployments} color="text-purple-500" bg="bg-purple-500/10" />
        <SummaryCard title="StatefulSets" icon={HardDrive} count={data.statefulsets} color="text-cyan-500" bg="bg-cyan-500/10" />
        <SummaryCard title="Services" icon={Network} count={data.services} color="text-orange-500" bg="bg-orange-500/10" />
        <SummaryCard title="Namespaces" icon={FolderOpen} count={{ total: data.namespaces.length, ready: data.namespaces.length, not_ready: 0, warning: 0 }} color="text-pink-500" bg="bg-pink-500/10" />
      </div>

      {/* Charts Row: Pod Status + Namespace Distribution */}
      <div className="grid gap-4 lg:grid-cols-2">
        <PodStatusChart breakdown={data.pod_status_breakdown} />
        <NamespacePodChart namespacePods={data.namespace_pod_counts} />
      </div>

      {/* Namespace Resource Usage */}
      {data.namespace_resource_usage.length > 0 && (
        <NamespaceResourceChart namespaces={data.namespace_resource_usage} nodeResources={data.node_resources} />
      )}

      {/* Node Resources */}
      {data.node_resources.length > 0 && (
        <NodeResourceChart nodes={data.node_resources} />
      )}

      {/* Workload Summary + Events */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Workload Status */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Box className="h-4 w-4" />
              Workload Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              <div className="grid grid-cols-[1fr_60px_60px_60px_60px] gap-2 px-2 py-1 text-sm font-medium text-muted-foreground">
                <span>Resource</span>
                <span className="text-center">Total</span>
                <span className="text-center">Ready</span>
                <span className="text-center">Not Ready</span>
                <span className="text-center">Warning</span>
              </div>
              <Separator />
              <WorkloadRow label="Deployments" count={data.deployments} />
              <WorkloadRow label="StatefulSets" count={data.statefulsets} />
              <WorkloadRow label="DaemonSets" count={data.daemonsets} />
              <WorkloadRow label="Jobs" count={data.jobs} />
              <WorkloadRow label="CronJobs" count={data.cronjobs} />
            </div>
          </CardContent>
        </Card>

        {/* Recent Events */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                Recent Events
              </CardTitle>
              <EventTypeSummary events={data.recent_events} />
            </div>
            <CardDescription className="text-sm">
              Latest cluster events
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.recent_events.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No recent events
              </p>
            ) : (
              <div className="space-y-2.5">
                {data.recent_events.slice(0, 8).map((event, i) => (
                  <EventRow key={`${event.name}-${i}`} event={event} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// ── Chart Components ────────────────────────────────────────────

const POD_STATUS_COLORS: Record<string, string> = {
  Running: "#22c55e",
  Succeeded: "#3b82f6",
  Pending: "#f59e0b",
  Failed: "#ef4444",
  Unknown: "#6b7280",
}

const POD_STATUS_DESCRIPTIONS: Record<string, string> = {
  Running: "Pod is bound to a node and all containers are running. At least one container is still in a running state.",
  Succeeded: "All containers in the pod have terminated successfully and will not be restarted.",
  Pending: "Pod has been accepted by the cluster but one or more containers are not yet running. This includes time waiting for scheduling or downloading images.",
  Failed: "All containers in the pod have terminated, and at least one container terminated with a non-zero exit code or was terminated by the system.",
  Unknown: "The state of the pod could not be determined, typically due to a communication error with the node.",
}

function PodStatusChart({ breakdown }: { breakdown: ClusterOverviewType["pod_status_breakdown"] }) {
  const chartData = useMemo(() => {
    const entries = [
      { name: "Running", value: breakdown.running },
      { name: "Succeeded", value: breakdown.succeeded },
      { name: "Pending", value: breakdown.pending },
      { name: "Failed", value: breakdown.failed },
      { name: "Unknown", value: breakdown.unknown },
    ]
    return entries.filter((e) => e.value > 0)
  }, [breakdown])

  const total = chartData.reduce((sum, d) => sum + d.value, 0)

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Container className="h-4 w-4" />
          Pod Status Distribution
        </CardTitle>
        <CardDescription className="text-sm">{total} total pods</CardDescription>
      </CardHeader>
      <CardContent>
        {total === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">No pods</p>
        ) : (
          <div className="flex items-center gap-6">
            <div className="w-[180px] h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    dataKey="value"
                    stroke="none"
                  >
                    {chartData.map((entry) => (
                      <Cell key={entry.name} fill={POD_STATUS_COLORS[entry.name]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ fontSize: 13, borderRadius: 8, border: "1px solid #e5e7eb" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2 flex-1">
              {chartData.map((entry) => (
                <div
                  key={entry.name}
                  className="flex items-center justify-between text-sm cursor-help"
                  title={POD_STATUS_DESCRIPTIONS[entry.name] || ""}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block w-3 h-3 rounded-sm"
                      style={{ backgroundColor: POD_STATUS_COLORS[entry.name] }}
                    />
                    <span className="underline decoration-dotted decoration-muted-foreground underline-offset-4">{entry.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{entry.value}</span>
                    <span className="text-muted-foreground w-10 text-right">
                      {Math.round((entry.value / total) * 100)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

const NS_COLORS = [
  "#3b82f6", "#8b5cf6", "#22c55e", "#f59e0b", "#ef4444",
  "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#6366f1",
]

function NamespacePodChart({ namespacePods }: { namespacePods: ClusterOverviewType["namespace_pod_counts"] }) {
  const chartData = useMemo(() => {
    const top = namespacePods.slice(0, 10)
    return top.map((ns) => ({ name: ns.namespace, count: ns.count }))
  }, [namespacePods])

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <FolderOpen className="h-4 w-4" />
          Pods by Namespace
        </CardTitle>
        <CardDescription className="text-sm">Top {chartData.length} namespaces</CardDescription>
      </CardHeader>
      <CardContent>
        {chartData.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">No data</p>
        ) : (
          <div className="h-[180px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 16, top: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 12 }}
                  width={120}
                />
                <Tooltip
                  contentStyle={{ fontSize: 13, borderRadius: 8, border: "1px solid #e5e7eb" }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={NS_COLORS[i % NS_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function NamespaceResourceChart({ namespaces, nodeResources }: { namespaces: ClusterOverviewType["namespace_resource_usage"]; nodeResources: NodeResourceInfo[] }) {
  const { chartData, clusterCpu, clusterMemory } = useMemo(() => {
    const all = namespaces.map((ns) => ({
      namespace: ns.namespace,
      cpu: parseCpuDisplay(ns.cpu_usage),
      cpuReq: parseCpuDisplay(ns.cpu_requested),
      memory: parseMemoryDisplay(ns.memory_usage),
      memReq: parseMemoryDisplay(ns.memory_requested),
      pods: ns.pod_count,
      cpuLabel: ns.cpu_usage,
      cpuReqLabel: ns.cpu_requested,
      memoryLabel: ns.memory_usage,
      memReqLabel: ns.memory_requested,
    }))
    // Total allocatable from all nodes
    const cCpu = nodeResources.reduce((sum, n) => sum + parseCpu(n.cpu_allocatable), 0)
    const cMem = nodeResources.reduce((sum, n) => sum + parseMemoryGi(n.memory_allocatable), 0) * 1024 // to MiB
    return { chartData: all.slice(0, 15), clusterCpu: cCpu, clusterMemory: cMem }
  }, [namespaces, nodeResources])

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <FolderOpen className="h-4 w-4" />
          Namespace Resource Usage
        </CardTitle>
        <CardDescription className="text-sm">
          CPU and memory usage per namespace (Top {chartData.length}) — Cluster allocatable: {clusterCpu} cores, {clusterMemory >= 1024 ? `${(clusterMemory / 1024).toFixed(1)}Gi` : `${Math.round(clusterMemory)}Mi`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left py-2 px-3 text-sm font-medium">Namespace</th>
                <th className="text-right py-2 px-3 text-sm font-medium">Pods</th>
                <th className="text-right py-2 px-3 text-sm font-medium">CPU</th>
                <th className="text-left py-2 px-3 text-sm font-medium w-[120px]"></th>
                <th className="text-right py-2 px-3 text-sm font-medium w-[50px] cursor-help" title="Percentage of cluster total allocatable CPU">%</th>
                <th className="text-right py-2 px-3 text-sm font-medium">Memory</th>
                <th className="text-left py-2 px-3 text-sm font-medium w-[120px]"></th>
                <th className="text-right py-2 px-3 text-sm font-medium w-[50px] cursor-help" title="Percentage of cluster total allocatable memory">%</th>
              </tr>
            </thead>
            <tbody>
              {chartData.map((ns) => {
                const maxCpu = chartData[0]?.cpu || 1
                const maxMem = chartData.reduce((max, d) => Math.max(max, d.memory), 1)
                const cpuBarPct = maxCpu > 0 ? (ns.cpu / maxCpu) * 100 : 0
                const memBarPct = maxMem > 0 ? (ns.memory / maxMem) * 100 : 0
                const cpuSharePct = clusterCpu > 0 ? (ns.cpu / clusterCpu) * 100 : 0
                const memSharePct = clusterMemory > 0 ? (ns.memory / clusterMemory) * 100 : 0

                return (
                  <tr key={ns.namespace} className="border-b last:border-b-0 hover:bg-muted/30">
                    <td className="py-1.5 px-3 font-medium font-mono">{ns.namespace}</td>
                    <td className="py-1.5 px-3 text-right text-muted-foreground">{ns.pods}</td>
                    <td className="py-1.5 px-3 text-right whitespace-nowrap">{ns.cpuLabel} / {ns.cpuReqLabel} cores</td>
                    <td className="py-1.5 px-3">
                      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-blue-500" style={{ width: `${cpuBarPct}%` }} />
                      </div>
                    </td>
                    <td className="py-1.5 px-3 text-right text-muted-foreground">{cpuSharePct.toFixed(1)}%</td>
                    <td className="py-1.5 px-3 text-right whitespace-nowrap">{ns.memoryLabel} / {ns.memReqLabel}</td>
                    <td className="py-1.5 px-3">
                      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-purple-500" style={{ width: `${memBarPct}%` }} />
                      </div>
                    </td>
                    <td className="py-1.5 px-3 text-right text-muted-foreground">{memSharePct.toFixed(1)}%</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

function NodeResourceChart({ nodes }: { nodes: NodeResourceInfo[] }) {
  const chartData = useMemo(() => {
    return nodes.map((n) => ({
      fullName: n.name,
      cpuUsage: parseCpu(n.cpu_usage),
      cpuAllocatable: parseCpu(n.cpu_allocatable),
      memoryUsage: parseMemoryGi(n.memory_usage),
      memoryAllocatable: parseMemoryGi(n.memory_allocatable),
      podsRunning: n.pods_running,
      podsAllocatable: parseInt(n.pods_allocatable) || 0,
      ready: n.ready,
    }))
  }, [nodes])

  const hasMetrics = chartData.some((n) => n.cpuUsage > 0 || n.memoryUsage > 0)

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Server className="h-4 w-4" />
          Node Resources {hasMetrics ? "(Usage / Allocatable)" : "(Allocatable / Capacity)"}
        </CardTitle>
        <CardDescription className="text-sm">{nodes.length} nodes</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left py-2 px-3 text-sm font-medium">Node</th>
                <th className="text-left py-2 px-3 text-sm font-medium">Status</th>
                <th className="text-left py-2 px-3 text-sm font-medium">CPU</th>
                <th className="text-left py-2 px-3 text-sm font-medium">Memory</th>
                <th className="text-left py-2 px-3 text-sm font-medium">Pods</th>
              </tr>
            </thead>
            <tbody>
              {chartData.map((n) => {
                const cpuPct = n.cpuAllocatable > 0 ? Math.round((n.cpuUsage / n.cpuAllocatable) * 100) : 0
                const memPct = n.memoryAllocatable > 0 ? Math.round((n.memoryUsage / n.memoryAllocatable) * 100) : 0

                return (
                  <tr key={n.fullName} className="border-b last:border-b-0 hover:bg-muted/30">
                    <td className="py-2 px-3 font-medium font-mono">{n.fullName}</td>
                    <td className="py-2 px-3">
                      <Badge
                        variant="outline"
                        className={`text-sm px-1.5 py-0 ${
                          n.ready
                            ? "bg-green-500/10 text-green-600 border-green-500/20"
                            : "bg-red-500/10 text-red-600 border-red-500/20"
                        }`}
                      >
                        {n.ready ? "Ready" : "NotReady"}
                      </Badge>
                    </td>
                    <td className="py-2 px-3">
                      {hasMetrics ? (
                        <ResourceBar
                          value={n.cpuUsage}
                          max={n.cpuAllocatable}
                          label={`${n.cpuUsage.toFixed(1)} / ${n.cpuAllocatable} cores (${cpuPct}%)`}
                          color={cpuPct > 80 ? "bg-red-500" : cpuPct > 60 ? "bg-amber-500" : "bg-blue-500"}
                        />
                      ) : (
                        <span className="text-muted-foreground">{n.cpuAllocatable} cores</span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      {hasMetrics ? (
                        <ResourceBar
                          value={n.memoryUsage}
                          max={n.memoryAllocatable}
                          label={`${n.memoryUsage.toFixed(1)} / ${n.memoryAllocatable.toFixed(1)} Gi (${memPct}%)`}
                          color={memPct > 80 ? "bg-red-500" : memPct > 60 ? "bg-amber-500" : "bg-purple-500"}
                        />
                      ) : (
                        <span className="text-muted-foreground">{n.memoryAllocatable.toFixed(1)} Gi</span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      <ResourceBar
                        value={n.podsRunning}
                        max={n.podsAllocatable}
                        label={`${n.podsRunning} / ${n.podsAllocatable}`}
                        color={n.podsAllocatable > 0 && (n.podsRunning / n.podsAllocatable) > 0.8 ? "bg-red-500" : "bg-green-500"}
                        tooltip={`${n.podsAllocatable} is the maximum number of pods that can be scheduled on this node (kubelet --max-pods setting, default 110).`}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

function ResourceBar({ value, max, label, color, tooltip }: { value: number; max: number; label: string; color: string; tooltip?: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0

  return (
    <div className="space-y-1">
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-sm text-muted-foreground${tooltip ? " cursor-help" : ""}`} title={tooltip}>{label}</span>
    </div>
  )
}

function EventTypeSummary({ events }: { events: K8sEvent[] }) {
  const warnings = events.filter((e) => e.type === "Warning").length
  const normals = events.length - warnings

  return (
    <div className="flex items-center gap-2">
      {warnings > 0 && (
        <Badge variant="outline" className="text-sm px-1.5 py-0 bg-amber-500/10 text-amber-600 border-amber-500/20">
          {warnings} Warning
        </Badge>
      )}
      <Badge variant="outline" className="text-sm px-1.5 py-0 bg-blue-500/10 text-blue-600 border-blue-500/20">
        {normals} Normal
      </Badge>
    </div>
  )
}

// ── Sub-components ───────────────────────────────────────────────

function SummaryCard({
  title,
  icon: Icon,
  count,
  color,
  bg,
}: {
  title: string
  icon: React.ComponentType<{ className?: string }>
  count: ResourceCount
  color: string
  bg: string
}) {
  const percentage = count.total > 0 ? Math.round((count.ready / count.total) * 100) : 0

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <div className={`rounded-md p-1.5 ${bg}`}>
          <Icon className={`h-4 w-4 ${color}`} />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-bold">{count.ready}</span>
          <span className="text-sm text-muted-foreground">/ {count.total}</span>
        </div>
        <div className="mt-1.5 h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              percentage === 100 ? "bg-green-500" : percentage > 50 ? "bg-amber-500" : "bg-red-500"
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>
        {count.not_ready > 0 && (
          <span className="text-sm text-red-500 mt-1 inline-block">
            {count.not_ready} not ready
          </span>
        )}
        {count.warning > 0 && (
          <span className="text-sm text-amber-500 mt-1 inline-block ml-2">
            {count.warning} pending
          </span>
        )}
      </CardContent>
    </Card>
  )
}

function WorkloadRow({ label, count }: { label: string; count: ResourceCount }) {
  return (
    <div className="grid grid-cols-[1fr_60px_60px_60px_60px] gap-2 items-center px-2 py-1.5 rounded-md hover:bg-muted/50 transition-colors">
      <span className="text-sm">{label}</span>
      <span className="text-center text-sm font-medium">{count.total}</span>
      <span className="text-center text-sm text-green-600 dark:text-green-400 font-medium">
        {count.ready}
      </span>
      <span
        className={`text-center text-sm font-medium ${
          count.not_ready > 0 ? "text-red-600 dark:text-red-400" : "text-muted-foreground"
        }`}
      >
        {count.not_ready}
      </span>
      <span
        className={`text-center text-sm font-medium ${
          count.warning > 0 ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"
        }`}
      >
        {count.warning}
      </span>
    </div>
  )
}

function EventRow({ event }: { event: K8sEvent }) {
  const isWarning = event.type === "Warning"
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5 min-w-0">
          <div className="flex items-center gap-1.5">
            <Badge
              variant="outline"
              className={`text-sm px-1 py-0 ${
                isWarning
                  ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                  : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
              }`}
            >
              {event.type}
            </Badge>
            <span className="text-sm font-medium text-muted-foreground truncate">
              {event.involved_kind}/{event.involved_name}
            </span>
          </div>
          <span className="text-sm leading-tight truncate">{event.message}</span>
        </div>
        <span className="text-sm text-muted-foreground whitespace-nowrap flex items-center gap-0.5">
          <Clock className="h-2.5 w-2.5" />
          {formatAge(event.last_timestamp)}
        </span>
      </div>
      <Separator className="mt-1" />
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────

function parseCpuDisplay(value: string): number {
  // Parse cores value like "0.14", "1.5" to number
  if (!value || value === "0") return 0
  return parseFloat(value) || 0
}

function parseMemoryDisplay(value: string): number {
  // Parse display values like "1609Mi", "1.5Gi" to MiB number
  if (!value || value === "0") return 0
  if (value.endsWith("Gi")) return parseFloat(value) * 1024
  if (value.endsWith("Mi")) return parseInt(value)
  if (value.endsWith("Ki")) return parseInt(value) / 1024
  return parseInt(value)
}

function parseCpu(value: string): number {
  if (!value) return 0
  if (value.endsWith("n")) return parseInt(value) / 1_000_000_000
  if (value.endsWith("u")) return parseInt(value) / 1_000_000
  if (value.endsWith("m")) return parseInt(value) / 1000
  return parseFloat(value) || 0
}

function parseMemoryGi(value: string): number {
  if (!value) return 0
  const num = parseInt(value)
  if (value.endsWith("Ki")) return num / (1024 * 1024)
  if (value.endsWith("Mi")) return num / 1024
  if (value.endsWith("Gi")) return num
  if (value.endsWith("Ti")) return num * 1024
  return num / (1024 * 1024 * 1024) // bytes
}

// ── Skeleton ────────────────────────────────────────────────────

function ClusterOverviewSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-6 w-48" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[120px]" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-[260px]" />
        <Skeleton className="h-[260px]" />
      </div>
      <Skeleton className="h-[300px]" />
      <Skeleton className="h-[200px]" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-[300px]" />
        <Skeleton className="h-[300px]" />
      </div>
    </div>
  )
}
