"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  Cpu,
  HardDrive,
  MemoryStick,
  Network,
  Server,
  Terminal,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Separator } from "@workspace/ui/components/separator"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@workspace/ui/components/tabs"
import { authFetch } from "@/features/auth/auth-fetch"
import type { K8sResourceItem } from "../types"
import { formatAge } from "../lib/formatters"
import { StatusBadge } from "./status-badge"

interface NodeAgentViewProps {
  node: K8sResourceItem
}

interface AgentInfo {
  id: string
  hostname: string
  ip_address: string
  status: string
}

interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  memory_total: number
  memory_used: number
  disk_percent: number
  disk_total: number
  disk_used: number
  net_bytes_sent: number
  net_bytes_recv: number
}

/**
 * Integrated view that shows K8s node info + matched Argus agent metrics.
 * Matches node by IP address or hostname.
 */
export function NodeAgentView({ node }: NodeAgentViewProps) {
  const [agent, setAgent] = useState<AgentInfo | null>(null)
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [agentLoading, setAgentLoading] = useState(true)

  const nodeStatus = node.status as Record<string, unknown> | undefined
  const nodeInfo = nodeStatus?.nodeInfo as Record<string, unknown> | undefined
  const addresses = nodeStatus?.addresses as Array<{ type: string; address: string }> | undefined
  const conditions = nodeStatus?.conditions as Array<Record<string, unknown>> | undefined

  const nodeIP = addresses?.find((a) => a.type === "InternalIP")?.address || ""
  const nodeHostname = addresses?.find((a) => a.type === "Hostname")?.address || node.metadata.name

  // Try to find a matching agent
  useEffect(() => {
    async function findAgent() {
      try {
        const res = await authFetch("/api/v1/agent/list")
        if (!res.ok) return
        const data = await res.json()
        const agents = data.agents || data || []

        const matched = agents.find((a: AgentInfo) =>
          a.ip_address === nodeIP || a.hostname === nodeHostname,
        )
        if (matched) {
          setAgent(matched)
          // Fetch metrics
          const metricsRes = await authFetch(`/api/v1/proxy/${matched.id}/monitor/system`)
          if (metricsRes.ok) {
            setMetrics(await metricsRes.json())
          }
        }
      } catch {
        // Agent matching is best-effort
      } finally {
        setAgentLoading(false)
      }
    }
    findAgent()
  }, [nodeIP, nodeHostname])

  const capacity = (node.spec as Record<string, unknown>)?.capacity as Record<string, string> | undefined
  const allocatable = nodeStatus?.allocatable as Record<string, string> | undefined

  return (
    <Tabs defaultValue="k8s">
      <TabsList>
        <TabsTrigger value="k8s">K8s Info</TabsTrigger>
        <TabsTrigger value="agent">
          Agent Monitoring
          {agent && (
            <span className="ml-1.5 inline-block w-1.5 h-1.5 rounded-full bg-green-500" />
          )}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="k8s" className="space-y-4 mt-4">
        {/* Node Info */}
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm">Node Info</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2 text-sm">
            <InfoRow label="OS Image" value={String(nodeInfo?.osImage || "")} />
            <InfoRow label="Architecture" value={String(nodeInfo?.architecture || "")} />
            <InfoRow label="Kernel Version" value={String(nodeInfo?.kernelVersion || "")} />
            <InfoRow label="Container Runtime" value={String(nodeInfo?.containerRuntimeVersion || "")} />
            <InfoRow label="Kubelet Version" value={String(nodeInfo?.kubeletVersion || "")} />
            <InfoRow label="Kube-Proxy Version" value={String(nodeInfo?.kubeProxyVersion || "")} />
          </CardContent>
        </Card>

        {/* Capacity & Allocatable */}
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Capacity</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-1">
              {capacity && Object.entries(capacity).map(([k, v]) => (
                <InfoRow key={k} label={k} value={v} />
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Allocatable</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-1">
              {allocatable && Object.entries(allocatable as Record<string, string>).map(([k, v]) => (
                <InfoRow key={k} label={k} value={v} />
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Conditions */}
        {conditions && (
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Conditions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {conditions.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <StatusBadge
                      status={c.status === "True" && c.type === "Ready" ? "Ready" :
                              c.status === "False" && c.type !== "Ready" ? "OK" :
                              c.status === "True" && c.type !== "Ready" ? String(c.type) : "NotReady"}
                    />
                    <span className="font-medium">{String(c.type)}</span>
                    <span className="text-muted-foreground text-xs">{String(c.message || "")}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </TabsContent>

      <TabsContent value="agent" className="space-y-4 mt-4">
        {agentLoading ? (
          <p className="text-sm text-muted-foreground p-4">Searching for matching agent...</p>
        ) : !agent ? (
          <Card>
            <CardContent className="py-8 text-center">
              <Server className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">
                No Argus agent matched for this node.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Looking for IP: {nodeIP} or hostname: {nodeHostname}
              </p>
              <Link href="/dashboard/server-management" prefetch={false}>
                <Button variant="outline" size="sm" className="mt-3">
                  Go to Server Management
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Agent Info */}
            <div className="flex items-center gap-3 text-sm">
              <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-500/20">
                Agent Connected
              </Badge>
              <span className="text-muted-foreground">
                {agent.hostname} ({agent.ip_address})
              </span>
              <Link
                href={`/dashboard/terminal?agentId=${agent.id}`}
                prefetch={false}
              >
                <Button variant="outline" size="sm" className="h-7">
                  <Terminal className="h-3.5 w-3.5 mr-1" />
                  Open Terminal
                </Button>
              </Link>
            </div>

            {/* Real-time Metrics */}
            {metrics ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="CPU"
                  icon={Cpu}
                  value={metrics.cpu_percent}
                  unit="%"
                  color="blue"
                />
                <MetricCard
                  label="Memory"
                  icon={MemoryStick}
                  value={metrics.memory_percent}
                  unit="%"
                  detail={`${formatBytesGB(metrics.memory_used)} / ${formatBytesGB(metrics.memory_total)}`}
                  color="green"
                />
                <MetricCard
                  label="Disk"
                  icon={HardDrive}
                  value={metrics.disk_percent}
                  unit="%"
                  detail={`${formatBytesGB(metrics.disk_used)} / ${formatBytesGB(metrics.disk_total)}`}
                  color="purple"
                />
                <MetricCard
                  label="Network"
                  icon={Network}
                  value={0}
                  unit=""
                  detail={`\u2191 ${formatBytesSpeed(metrics.net_bytes_sent)} \u2193 ${formatBytesSpeed(metrics.net_bytes_recv)}`}
                  color="orange"
                  hideBar
                />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Could not load agent metrics.</p>
            )}
          </>
        )}
      </TabsContent>
    </Tabs>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-muted-foreground w-36 shrink-0">{label}:</span>
      <span className="font-mono text-xs break-all">{value}</span>
    </div>
  )
}

function MetricCard({
  label,
  icon: Icon,
  value,
  unit,
  detail,
  color,
  hideBar,
}: {
  label: string
  icon: React.ComponentType<{ className?: string }>
  value: number
  unit: string
  detail?: string
  color: string
  hideBar?: boolean
}) {
  const colorMap: Record<string, { text: string; bg: string; bar: string }> = {
    blue: { text: "text-blue-500", bg: "bg-blue-500/10", bar: "bg-blue-500" },
    green: { text: "text-green-500", bg: "bg-green-500/10", bar: "bg-green-500" },
    purple: { text: "text-purple-500", bg: "bg-purple-500/10", bar: "bg-purple-500" },
    orange: { text: "text-orange-500", bg: "bg-orange-500/10", bar: "bg-orange-500" },
  }
  const c = colorMap[color] || colorMap.blue

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-muted-foreground">{label}</span>
          <div className={`rounded-md p-1 ${c.bg}`}>
            <Icon className={`h-3.5 w-3.5 ${c.text}`} />
          </div>
        </div>
        {!hideBar && (
          <>
            <div className="text-xl font-bold">
              {Math.round(value)}{unit}
            </div>
            <div className="mt-1.5 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${c.bar}`}
                style={{ width: `${Math.min(value, 100)}%` }}
              />
            </div>
          </>
        )}
        {detail && (
          <p className="text-xs text-muted-foreground mt-1">{detail}</p>
        )}
      </CardContent>
    </Card>
  )
}

function formatBytesGB(bytes: number): string {
  if (!bytes) return "0 GB"
  return `${(bytes / 1073741824).toFixed(1)} GB`
}

function formatBytesSpeed(bytes: number): string {
  if (!bytes) return "0 B/s"
  if (bytes < 1024) return `${bytes} B/s`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB/s`
  return `${(bytes / 1048576).toFixed(1)} MB/s`
}
