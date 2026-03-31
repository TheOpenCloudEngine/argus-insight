"use client"

import {
  Box,
  CheckCircle2,
  Clock,
  Container,
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
import type { ClusterOverview as ClusterOverviewType, ResourceCount, K8sEvent } from "../types"
import { useClusterOverview } from "../hooks/use-k8s-resources"
import { formatAge, getStatusBgColor } from "../lib/formatters"

export function ClusterOverview() {
  const { data, loading, error } = useClusterOverview()

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
        <XCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
        <p className="text-sm font-medium text-destructive">Cluster Connection Failed</p>
        <p className="text-xs text-muted-foreground mt-1">{error}</p>
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
        <p className="text-xs text-muted-foreground mt-1">{data.cluster.error}</p>
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

      {/* Summary Cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Nodes"
          icon={Server}
          count={data.nodes}
          color="text-blue-500"
          bg="bg-blue-500/10"
        />
        <SummaryCard
          title="Pods"
          icon={Container}
          count={data.pods}
          color="text-green-500"
          bg="bg-green-500/10"
        />
        <SummaryCard
          title="Deployments"
          icon={Layers}
          count={data.deployments}
          color="text-purple-500"
          bg="bg-purple-500/10"
        />
        <SummaryCard
          title="Services"
          icon={Network}
          count={data.services}
          color="text-orange-500"
          bg="bg-orange-500/10"
        />
      </div>

      {/* Workload Summary + Events */}
      <div className="grid gap-4 lg:grid-cols-5">
        {/* Workload Status */}
        <Card className="lg:col-span-3">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Box className="h-4 w-4" />
              Workload Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              <div className="grid grid-cols-[1fr_60px_60px_60px_60px] gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
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
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Recent Events
            </CardTitle>
            <CardDescription className="text-xs">
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
          <span className="text-xs text-red-500 mt-1 inline-block">
            {count.not_ready} not ready
          </span>
        )}
        {count.warning > 0 && (
          <span className="text-xs text-amber-500 mt-1 inline-block ml-2">
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
              className={`text-[10px] px-1 py-0 ${
                isWarning
                  ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                  : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
              }`}
            >
              {event.type}
            </Badge>
            <span className="text-xs font-medium text-muted-foreground truncate">
              {event.involved_kind}/{event.involved_name}
            </span>
          </div>
          <span className="text-xs leading-tight truncate">{event.message}</span>
        </div>
        <span className="text-[10px] text-muted-foreground whitespace-nowrap flex items-center gap-0.5">
          <Clock className="h-2.5 w-2.5" />
          {formatAge(event.last_timestamp)}
        </span>
      </div>
      <Separator className="mt-1" />
    </div>
  )
}

function ClusterOverviewSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-6 w-48" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-[120px]" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-5">
        <Skeleton className="h-[300px] lg:col-span-3" />
        <Skeleton className="h-[300px] lg:col-span-2" />
      </div>
    </div>
  )
}
