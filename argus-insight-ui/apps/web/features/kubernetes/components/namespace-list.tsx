"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { RefreshCw, Search } from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { DashboardHeader } from "@/components/dashboard-header"
import { fetchNamespaceUsage, listResources } from "../api"
import type { K8sResourceItem } from "../types"
import type { NamespaceResourceUsage } from "../types"
import { RESOURCE_URL_MAP } from "../lib/resource-definitions"
import { formatAge } from "../lib/formatters"
import { StatusBadge } from "./status-badge"

interface NamespaceRow {
  name: string
  status: string
  creationTimestamp: string
  item: K8sResourceItem
  usage: NamespaceResourceUsage | null
}

export function NamespaceList() {
  const [items, setItems] = useState<K8sResourceItem[]>([])
  const [usage, setUsage] = useState<NamespaceResourceUsage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nsData, usageData] = await Promise.all([
        listResources("namespaces"),
        fetchNamespaceUsage().catch(() => []),
      ])
      setItems(nsData.items)
      setUsage(usageData)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load namespaces")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const usageMap = useMemo(() => {
    const map = new Map<string, NamespaceResourceUsage>()
    for (const u of usage) {
      map.set(u.namespace, u)
    }
    return map
  }, [usage])

  const rows: NamespaceRow[] = useMemo(() => {
    return items
      .map((item) => {
        const name = item.metadata.name
        const status = ((item.status as Record<string, unknown>)?.phase as string) || "Active"
        return {
          name,
          status,
          creationTimestamp: item.metadata.creationTimestamp || "",
          item,
          usage: usageMap.get(name) || null,
        }
      })
      .filter((row) => {
        if (!search) return true
        return row.name.toLowerCase().includes(search.toLowerCase())
      })
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [items, usageMap, search])

  if (error) {
    return (
      <>
        <DashboardHeader title="Namespaces" />
        <div className="p-4">
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" size="sm" onClick={load} className="mt-2">Retry</Button>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <DashboardHeader title="Namespaces" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search namespaces..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-8 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {rows.length} namespace{rows.length !== 1 ? "s" : ""}
              </span>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={load}>
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-sm h-9">Name</TableHead>
                  <TableHead className="text-sm h-9">Status</TableHead>
                  <TableHead className="text-sm h-9 text-right">Pods</TableHead>
                  <TableHead className="text-sm h-9">CPU</TableHead>
                  <TableHead className="text-sm h-9 w-[140px]"></TableHead>
                  <TableHead className="text-sm h-9">Memory</TableHead>
                  <TableHead className="text-sm h-9 w-[140px]"></TableHead>
                  <TableHead className="text-sm h-9">Age</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 8 }).map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-20" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="h-24 text-center text-sm text-muted-foreground">
                      No namespaces found
                    </TableCell>
                  </TableRow>
                ) : (
                  rows.map((row) => (
                    <NamespaceTableRow key={row.name} row={row} />
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
    </>
  )
}

function NamespaceTableRow({ row }: { row: NamespaceRow }) {
  const u = row.usage
  const baseUrl = RESOURCE_URL_MAP["namespaces"]
  const href = `${baseUrl}/${encodeURIComponent(row.name)}`

  const cpuUsage = u ? parseCpu(u.cpu_usage) : 0
  const cpuReq = u ? parseCpu(u.cpu_requested) : 0
  const memUsage = u ? parseMem(u.memory_usage) : 0
  const memReq = u ? parseMem(u.memory_requested) : 0

  const cpuPct = cpuReq > 0 ? (cpuUsage / cpuReq) * 100 : 0
  const memPct = memReq > 0 ? (memUsage / memReq) * 100 : 0

  const cpuColor = cpuPct > 100 ? "bg-red-600" : cpuPct > 80 ? "bg-red-500" : cpuPct > 60 ? "bg-amber-500" : "bg-blue-500"
  const memColor = memPct > 100 ? "bg-red-600" : memPct > 80 ? "bg-red-500" : memPct > 60 ? "bg-amber-500" : "bg-purple-500"

  return (
    <TableRow>
      <TableCell className="py-1.5">
        <Link href={href} className="text-blue-600 dark:text-blue-400 hover:underline font-medium" prefetch={false}>
          {row.name}
        </Link>
      </TableCell>
      <TableCell className="py-1.5">
        <StatusBadge status={row.status} />
      </TableCell>
      <TableCell className="py-1.5 text-right text-muted-foreground">
        {u ? u.pod_count : "—"}
      </TableCell>
      <TableCell className="py-1.5 whitespace-nowrap">
        {u && cpuReq > 0
          ? <span>{u.cpu_usage} / {u.cpu_requested} cores</span>
          : u && cpuUsage > 0
            ? <span>{u.cpu_usage} cores</span>
            : <span className="text-muted-foreground">—</span>
        }
      </TableCell>
      <TableCell className="py-1.5">
        {u && cpuReq > 0 ? (
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
              <div className={`h-full rounded-full ${cpuColor}`} style={{ width: `${Math.min(cpuPct, 100)}%` }} />
            </div>
            <span className="text-muted-foreground w-10 text-right text-sm">{cpuPct.toFixed(0)}%</span>
          </div>
        ) : null}
      </TableCell>
      <TableCell className="py-1.5 whitespace-nowrap">
        {u && memReq > 0
          ? <span>{u.memory_usage} / {u.memory_requested}</span>
          : u && memUsage > 0
            ? <span>{u.memory_usage}</span>
            : <span className="text-muted-foreground">—</span>
        }
      </TableCell>
      <TableCell className="py-1.5">
        {u && memReq > 0 ? (
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
              <div className={`h-full rounded-full ${memColor}`} style={{ width: `${Math.min(memPct, 100)}%` }} />
            </div>
            <span className="text-muted-foreground w-10 text-right text-sm">{memPct.toFixed(0)}%</span>
          </div>
        ) : null}
      </TableCell>
      <TableCell className="py-1.5 text-muted-foreground text-sm">
        {formatAge(row.creationTimestamp)}
      </TableCell>
    </TableRow>
  )
}

// ── Helpers ──────────────────────────────────────────────────────

function parseCpu(value: string): number {
  if (!value || value === "0") return 0
  if (value.endsWith("m")) return parseInt(value) / 1000
  return parseFloat(value) || 0
}

function parseMem(value: string): number {
  if (!value || value === "0") return 0
  if (value.endsWith("Gi")) return parseFloat(value) * 1024
  if (value.endsWith("Mi")) return parseInt(value)
  if (value.endsWith("Ki")) return parseInt(value) / 1024
  return parseInt(value)
}
