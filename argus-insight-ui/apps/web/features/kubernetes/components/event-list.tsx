"use client"

import { useEffect, useState } from "react"
import { Badge } from "@workspace/ui/components/badge"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { listResources } from "../api"
import type { K8sResourceItem } from "../types"
import { formatAge } from "../lib/formatters"

interface EventListProps {
  namespace: string
  fieldSelector?: string
}

export function EventList({ namespace, fieldSelector }: EventListProps) {
  const [events, setEvents] = useState<K8sResourceItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params: Record<string, string> = {}
    if (fieldSelector) params.fieldSelector = fieldSelector

    listResources("events", namespace || undefined, params)
      .then((data) => {
        const sorted = [...data.items].sort((a, b) => {
          const aTime = (a as Record<string, unknown>).lastTimestamp as string || a.metadata.creationTimestamp || ""
          const bTime = (b as Record<string, unknown>).lastTimestamp as string || b.metadata.creationTimestamp || ""
          return bTime.localeCompare(aTime)
        })
        setEvents(sorted)
      })
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [namespace, fieldSelector])

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  if (events.length === 0) {
    return <p className="text-sm text-muted-foreground p-4 text-center">No events found</p>
  }

  return (
    <div className="rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left py-2 px-3 text-xs font-medium w-16">Type</th>
            <th className="text-left py-2 px-3 text-xs font-medium w-28">Reason</th>
            <th className="text-left py-2 px-3 text-xs font-medium">Object</th>
            <th className="text-left py-2 px-3 text-xs font-medium">Message</th>
            <th className="text-left py-2 px-3 text-xs font-medium w-16">Count</th>
            <th className="text-left py-2 px-3 text-xs font-medium w-16">Age</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, i) => {
            const e = event as Record<string, unknown>
            const involved = e.involvedObject as Record<string, unknown> | undefined
            const isWarning = e.type === "Warning"
            const lastTs = e.lastTimestamp as string || event.metadata.creationTimestamp || ""

            return (
              <tr key={`${event.metadata.uid || i}`} className="border-b last:border-b-0 hover:bg-muted/30">
                <td className="py-1.5 px-3">
                  <Badge
                    variant="outline"
                    className={`text-[10px] px-1 py-0 ${
                      isWarning
                        ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                        : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                    }`}
                  >
                    {String(e.type || "Normal")}
                  </Badge>
                </td>
                <td className="py-1.5 px-3 text-xs font-medium">{String(e.reason || "")}</td>
                <td className="py-1.5 px-3 text-xs text-muted-foreground">
                  {involved ? `${involved.kind}/${involved.name}` : ""}
                </td>
                <td className="py-1.5 px-3 text-xs max-w-[400px] truncate">{String(e.message || "")}</td>
                <td className="py-1.5 px-3 text-xs text-center">{Number(e.count || 1)}</td>
                <td className="py-1.5 px-3 text-xs text-muted-foreground">{formatAge(lastTs)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
