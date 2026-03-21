"use client"

import { useCallback, useEffect, useState } from "react"
import { ChevronRight, History, Loader2, Minus, Plus, RefreshCw } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Button } from "@workspace/ui/components/button"
import {
  fetchSchemaHistory,
  type SchemaSnapshot,
  type SchemaChangeEntry,
} from "@/features/datasets/api"

type SchemaHistoryTabProps = {
  datasetId: number
}

function ChangeTypeBadge({ type }: { type: string }) {
  if (type === "ADD") {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-green-600">
        <Plus className="h-3 w-3" /> ADD
      </span>
    )
  }
  if (type === "DROP") {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-red-500">
        <Minus className="h-3 w-3" /> DROP
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-orange-500">
      <RefreshCw className="h-3 w-3" /> MODIFY
    </span>
  )
}

function ChangeDetail({ change }: { change: SchemaChangeEntry }) {
  return (
    <div className="flex items-start gap-3 py-1.5 px-2 text-xs font-[family-name:var(--font-d2coding)]">
      <ChangeTypeBadge type={change.type} />
      <span className="font-medium min-w-[120px]">{change.field}</span>
      <div className="flex-1">
        {change.type === "ADD" && change.after && (
          <span className="text-green-600">
            {Object.entries(change.after).map(([k, v]) => `${k}=${v}`).join(", ")}
          </span>
        )}
        {change.type === "DROP" && change.before && (
          <span className="text-red-500 line-through">
            {Object.entries(change.before).map(([k, v]) => `${k}=${v}`).join(", ")}
          </span>
        )}
        {change.type === "MODIFY" && (
          <div className="flex gap-2">
            {change.before && (
              <span className="text-red-500 line-through">
                {Object.entries(change.before).map(([k, v]) => `${k}=${v}`).join(", ")}
              </span>
            )}
            <span className="text-muted-foreground">&rarr;</span>
            {change.after && (
              <span className="text-green-600">
                {Object.entries(change.after).map(([k, v]) => `${k}=${v}`).join(", ")}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function SnapshotItem({ snapshot }: { snapshot: SchemaSnapshot }) {
  const [open, setOpen] = useState(false)
  const date = new Date(snapshot.synced_at)
  const dateStr = date.toLocaleDateString("ko-KR", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  })

  return (
    <div className="border-l-2 border-muted pl-4 pb-4 relative">
      <div className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-primary" />
      <button
        type="button"
        className="flex items-center gap-2 text-sm hover:text-primary transition-colors w-full text-left"
        onClick={() => setOpen(!open)}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
        />
        <span className="font-medium font-[family-name:var(--font-d2coding)]">{dateStr}</span>
        <span className="text-muted-foreground text-xs">{snapshot.field_count} fields</span>
        {snapshot.change_summary && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-muted">
            {snapshot.change_summary}
          </span>
        )}
      </button>
      {open && snapshot.changes.length > 0 && (
        <div className="mt-2 border rounded bg-muted/20">
          {snapshot.changes.map((c, i) => (
            <div
              key={`${c.field}-${i}`}
              className={i > 0 ? "border-t" : ""}
            >
              <ChangeDetail change={c} />
            </div>
          ))}
        </div>
      )}
      {open && snapshot.changes.length === 0 && (
        <p className="mt-2 text-xs text-muted-foreground ml-6">Initial sync — no prior state to compare</p>
      )}
    </div>
  )
}

export function SchemaHistoryTab({ datasetId }: SchemaHistoryTabProps) {
  const [snapshots, setSnapshots] = useState<SchemaSnapshot[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [page, setPage] = useState(1)
  const pageSize = 20

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await fetchSchemaHistory(datasetId, page, pageSize)
      setSnapshots(data.items)
      setTotal(data.total)
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [datasetId, page])

  useEffect(() => {
    load()
  }, [load])

  const totalPages = Math.ceil(total / pageSize)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between py-3">
        <CardTitle className="text-base flex items-center gap-2">
          <History className="h-4 w-4" />
          Schema Change History
        </CardTitle>
        <span className="text-xs text-muted-foreground">{total} snapshot(s)</span>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : snapshots.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No schema history available. Run a sync to start tracking changes.
          </p>
        ) : (
          <>
            <div className="ml-1 mt-1">
              {snapshots.map((snap) => (
                <SnapshotItem key={snap.id} snapshot={snap} />
              ))}
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </Button>
                <span className="text-xs text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
