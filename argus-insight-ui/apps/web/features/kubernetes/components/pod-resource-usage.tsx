"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { authFetch } from "@/features/auth/auth-fetch"
import { RESOURCE_URL_MAP } from "../lib/resource-definitions"
import { formatAge } from "../lib/formatters"
import { StatusBadge } from "./status-badge"

interface PodMetricsItem {
  metadata: { name: string; namespace: string }
  containers: Array<{
    name: string
    usage: { cpu: string; memory: string }
  }>
}

interface PodInfo {
  name: string
  namespace: string
  status: string
  creationTimestamp: string
  cpuUsage: number
  cpuRequest: number
  cpuUsageRaw: string
  cpuRequestRaw: string
  memUsage: number
  memRequest: number
  memUsageRaw: string
  memRequestRaw: string
}

interface PodResourceUsageProps {
  namespace: string
}

export function PodResourceUsage({ namespace }: PodResourceUsageProps) {
  const [pods, setPods] = useState<PodInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        // Fetch pods and pod metrics in parallel
        const [podsRes, metricsRes] = await Promise.all([
          authFetch(`/api/v1/k8s/${encodeURIComponent(namespace)}/pods`),
          authFetch(`/api/v1/k8s/pod-metrics?namespace=${encodeURIComponent(namespace)}`).catch(() => null),
        ])

        const podsData = podsRes.ok ? await podsRes.json() : { items: [] }
        const metricsData = metricsRes?.ok ? await metricsRes.json() : { items: [] }

        // Build metrics map
        const metricsMap = new Map<string, { cpu: number; mem: number }>()
        for (const pm of (metricsData.items || []) as PodMetricsItem[]) {
          let cpu = 0
          let mem = 0
          for (const c of pm.containers || []) {
            cpu += parseCpuNano(c.usage?.cpu || "0")
            mem += parseMemBytes(c.usage?.memory || "0")
          }
          metricsMap.set(pm.metadata.name, { cpu, mem })
        }

        // Build pod list
        const result: PodInfo[] = []
        for (const pod of podsData.items || []) {
          const meta = pod.metadata || {}
          const spec = pod.spec || {}
          const status = pod.status || {}
          const phase = status.phase || "Unknown"
          const name = meta.name || ""

          // Aggregate requests from containers
          let cpuReq = 0
          let memReq = 0
          for (const c of spec.containers || []) {
            const req = c.resources?.requests || {}
            cpuReq += parseCpuNano(req.cpu || "0")
            memReq += parseMemBytes(req.memory || "0")
          }

          const usage = metricsMap.get(name) || { cpu: 0, mem: 0 }

          result.push({
            name,
            namespace,
            status: phase,
            creationTimestamp: meta.creationTimestamp || "",
            cpuUsage: usage.cpu,
            cpuRequest: cpuReq,
            cpuUsageRaw: formatCpuCores(usage.cpu),
            cpuRequestRaw: formatCpuCores(cpuReq),
            memUsage: usage.mem,
            memRequest: memReq,
            memUsageRaw: formatMemory(usage.mem),
            memRequestRaw: formatMemory(memReq),
          })
        }

        result.sort((a, b) => a.name.localeCompare(b.name))
        setPods(result)
      } catch {
        setPods([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [namespace])

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    )
  }

  if (pods.length === 0) {
    return <p className="text-sm text-muted-foreground text-center py-4">No pods in this namespace</p>
  }

  return (
    <div className="rounded-md border">
      <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-sm h-9">Pod</TableHead>
                <TableHead className="text-sm h-9">Status</TableHead>
                <TableHead className="text-sm h-9">CPU</TableHead>
                <TableHead className="text-sm h-9 w-[140px]"></TableHead>
                <TableHead className="text-sm h-9">Memory</TableHead>
                <TableHead className="text-sm h-9 w-[140px]"></TableHead>
                <TableHead className="text-sm h-9">Age</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pods.map((pod) => (
                <PodRow key={pod.name} pod={pod} />
              ))}
            </TableBody>
      </Table>
    </div>
  )
}

function PodRow({ pod }: { pod: PodInfo }) {
  const baseUrl = RESOURCE_URL_MAP["pods"]
  const href = `${baseUrl}/${encodeURIComponent(pod.name)}?namespace=${encodeURIComponent(pod.namespace)}`

  const cpuPct = pod.cpuRequest > 0 ? (pod.cpuUsage / pod.cpuRequest) * 100 : 0
  const memPct = pod.memRequest > 0 ? (pod.memUsage / pod.memRequest) * 100 : 0
  const cpuColor = cpuPct > 100 ? "bg-red-600" : cpuPct > 80 ? "bg-red-500" : cpuPct > 60 ? "bg-amber-500" : "bg-blue-500"
  const memColor = memPct > 100 ? "bg-red-600" : memPct > 80 ? "bg-red-500" : memPct > 60 ? "bg-amber-500" : "bg-purple-500"

  return (
    <TableRow>
      <TableCell className="py-1.5">
        <Link href={href} className="text-blue-600 dark:text-blue-400 hover:underline font-medium" prefetch={false}>
          {pod.name}
        </Link>
      </TableCell>
      <TableCell className="py-1.5">
        <StatusBadge status={pod.status} />
      </TableCell>
      <TableCell className="py-1.5 whitespace-nowrap">
        {pod.cpuRequest > 0
          ? <span>{pod.cpuUsageRaw} / {pod.cpuRequestRaw}</span>
          : pod.cpuUsage > 0
            ? <span>{pod.cpuUsageRaw}</span>
            : <span className="text-muted-foreground">—</span>
        }
      </TableCell>
      <TableCell className="py-1.5">
        {pod.cpuRequest > 0 ? (
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
              <div className={`h-full rounded-full ${cpuColor}`} style={{ width: `${Math.min(cpuPct, 100)}%` }} />
            </div>
            <span className="text-muted-foreground w-10 text-right text-sm">{cpuPct.toFixed(0)}%</span>
          </div>
        ) : null}
      </TableCell>
      <TableCell className="py-1.5 whitespace-nowrap">
        {pod.memRequest > 0
          ? <span>{pod.memUsageRaw} / {pod.memRequestRaw}</span>
          : pod.memUsage > 0
            ? <span>{pod.memUsageRaw}</span>
            : <span className="text-muted-foreground">—</span>
        }
      </TableCell>
      <TableCell className="py-1.5">
        {pod.memRequest > 0 ? (
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
              <div className={`h-full rounded-full ${memColor}`} style={{ width: `${Math.min(memPct, 100)}%` }} />
            </div>
            <span className="text-muted-foreground w-10 text-right text-sm">{memPct.toFixed(0)}%</span>
          </div>
        ) : null}
      </TableCell>
      <TableCell className="py-1.5 text-muted-foreground text-sm">
        {formatAge(pod.creationTimestamp)}
      </TableCell>
    </TableRow>
  )
}

// ── Helpers ──────────────────────────────────────────────────────

function parseCpuNano(value: string): number {
  if (!value || value === "0") return 0
  if (value.endsWith("n")) return parseInt(value)
  if (value.endsWith("u")) return parseInt(value) * 1000
  if (value.endsWith("m")) return parseInt(value) * 1_000_000
  return parseFloat(value) * 1_000_000_000
}

function parseMemBytes(value: string): number {
  if (!value || value === "0") return 0
  if (value.endsWith("Ki")) return parseInt(value) * 1024
  if (value.endsWith("Mi")) return parseInt(value) * 1024 * 1024
  if (value.endsWith("Gi")) return parseFloat(value) * 1024 * 1024 * 1024
  if (value.endsWith("Ti")) return parseFloat(value) * 1024 * 1024 * 1024 * 1024
  return parseInt(value)
}

function formatCpuCores(nanocores: number): string {
  const cores = nanocores / 1_000_000_000
  if (cores === 0) return "0"
  if (cores >= 10) return `${cores.toFixed(1)}`
  return `${cores.toFixed(2)}`
}

function formatMemory(bytes: number): string {
  if (bytes === 0) return "0"
  const mi = bytes / (1024 * 1024)
  if (mi >= 1024) return `${(mi / 1024).toFixed(1)}Gi`
  return `${Math.round(mi)}Mi`
}
