"use client"

import { useCallback, useEffect, useState } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { Card, CardContent } from "@workspace/ui/components/card"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { Bell, Check, Eye, X } from "lucide-react"
import { authFetch } from "@/features/auth/auth-fetch"

const BASE = "/api/v1/alerts"

type Alert = {
  id: number
  alert_type: string
  severity: string
  source_dataset_id: number
  source_dataset_name: string | null
  source_platform_type: string | null
  affected_dataset_id: number | null
  affected_dataset_name: string | null
  affected_platform_type: string | null
  lineage_id: number | null
  change_summary: string
  change_detail: string | null
  status: string
  resolved_by: string | null
  resolved_at: string | null
  created_at: string
}

type PaginatedAlerts = {
  items: Alert[]
  total: number
  page: number
  page_size: number
}

export default function AlertsPage() {
  const [data, setData] = useState<PaginatedAlerts | null>(null)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState("OPEN")
  const [severityFilter, setSeverityFilter] = useState("all")
  const [page, setPage] = useState(1)
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const fetchAlerts = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (statusFilter !== "all") params.set("status", statusFilter)
    if (severityFilter !== "all") params.set("severity", severityFilter)
    params.set("page", String(page))
    params.set("page_size", "20")

    try {
      const resp = await authFetch(`${BASE}?${params}`)
      if (resp.ok) setData(await resp.json())
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }, [statusFilter, severityFilter, page])

  useEffect(() => { fetchAlerts() }, [fetchAlerts])

  const updateStatus = async (alertId: number, status: string) => {
    await authFetch(`${BASE}/${alertId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    })
    fetchAlerts()
  }

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0

  return (
    <>
      <DashboardHeader title="Alerts" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Filters */}
        <div className="flex items-center gap-3">
          <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(1) }}>
            <SelectTrigger className="w-40 h-9">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="OPEN">Open</SelectItem>
              <SelectItem value="ACKNOWLEDGED">Acknowledged</SelectItem>
              <SelectItem value="RESOLVED">Resolved</SelectItem>
              <SelectItem value="DISMISSED">Dismissed</SelectItem>
            </SelectContent>
          </Select>

          <Select value={severityFilter} onValueChange={v => { setSeverityFilter(v); setPage(1) }}>
            <SelectTrigger className="w-40 h-9">
              <SelectValue placeholder="Severity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Severity</SelectItem>
              <SelectItem value="BREAKING">Breaking</SelectItem>
              <SelectItem value="WARNING">Warning</SelectItem>
              <SelectItem value="INFO">Info</SelectItem>
            </SelectContent>
          </Select>

          <div className="ml-auto text-sm text-muted-foreground">
            {data ? `${data.total} alert(s)` : ""}
          </div>
        </div>

        {/* Table */}
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-24">Severity</TableHead>
                  <TableHead>Change</TableHead>
                  <TableHead className="w-48">Source</TableHead>
                  <TableHead className="w-48">Affected</TableHead>
                  <TableHead className="w-28">Status</TableHead>
                  <TableHead className="w-32">Time</TableHead>
                  <TableHead className="w-28">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                      Loading...
                    </TableCell>
                  </TableRow>
                ) : !data || data.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-12">
                      <Bell className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
                      <p className="text-sm text-muted-foreground">No alerts found</p>
                    </TableCell>
                  </TableRow>
                ) : (
                  data.items.map(alert => (
                    <TableRow key={alert.id} className="cursor-pointer hover:bg-muted/50"
                      onClick={() => { setSelectedAlert(alert); setDetailOpen(true) }}
                    >
                      <TableCell>
                        <SeverityBadge severity={alert.severity} />
                      </TableCell>
                      <TableCell>
                        <p className="text-sm truncate max-w-sm">{alert.change_summary}</p>
                      </TableCell>
                      <TableCell>
                        <div className="text-xs">
                          <span className="text-muted-foreground">{alert.source_platform_type}</span>
                          <p className="font-medium truncate">{alert.source_dataset_name}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        {alert.affected_dataset_name ? (
                          <div className="text-xs">
                            <span className="text-muted-foreground">{alert.affected_platform_type}</span>
                            <p className="font-medium truncate">{alert.affected_dataset_name}</p>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={alert.status} />
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {formatTimeAgo(alert.created_at)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                          {alert.status === "OPEN" && (
                            <>
                              <Button
                                variant="ghost" size="icon" className="h-7 w-7"
                                title="Acknowledge"
                                onClick={() => updateStatus(alert.id, "ACKNOWLEDGED")}
                              >
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost" size="icon" className="h-7 w-7"
                                title="Resolve"
                                onClick={() => updateStatus(alert.id, "RESOLVED")}
                              >
                                <Check className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost" size="icon" className="h-7 w-7"
                                title="Dismiss"
                                onClick={() => updateStatus(alert.id, "DISMISSED")}
                              >
                                <X className="h-3.5 w-3.5" />
                              </Button>
                            </>
                          )}
                          {alert.status === "ACKNOWLEDGED" && (
                            <Button
                              variant="ghost" size="icon" className="h-7 w-7"
                              title="Resolve"
                              onClick={() => updateStatus(alert.id, "RESOLVED")}
                            >
                              <Check className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button
              variant="outline" size="sm"
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline" size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </div>

      {/* Alert Detail Dialog */}
      <AlertDialog open={detailOpen} onOpenChange={setDetailOpen}>
        <AlertDialogContent className="max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              Alert Detail
              {selectedAlert && <SeverityBadge severity={selectedAlert.severity} />}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 pt-2">
                {selectedAlert && (
                  <>
                    <div>
                      <span className="text-xs text-muted-foreground">Change</span>
                      <p className="text-sm font-medium">{selectedAlert.change_summary}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <span className="text-xs text-muted-foreground">Source</span>
                        <p className="text-sm">
                          {selectedAlert.source_platform_type}.{selectedAlert.source_dataset_name}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground">Affected</span>
                        <p className="text-sm">
                          {selectedAlert.affected_dataset_name
                            ? `${selectedAlert.affected_platform_type}.${selectedAlert.affected_dataset_name}`
                            : "-"}
                        </p>
                      </div>
                    </div>

                    <div>
                      <span className="text-xs text-muted-foreground">Status</span>
                      <div className="mt-1">
                        <StatusBadge status={selectedAlert.status} />
                      </div>
                    </div>

                    {selectedAlert.change_detail && (
                      <div>
                        <span className="text-xs text-muted-foreground">Detail</span>
                        <div className="mt-1 max-h-48 overflow-y-auto">
                          {(() => {
                            try {
                              const details = JSON.parse(selectedAlert.change_detail!)
                              return (
                                <div className="space-y-1.5">
                                  {details.map((d: Record<string, string>, i: number) => (
                                    <div key={i} className="text-xs bg-muted/50 rounded px-3 py-2">
                                      <span className="font-medium">{d.changed_column || d.field}</span>
                                      <span className="text-muted-foreground ml-1">
                                        ({d.change_type || d.type})
                                      </span>
                                      {d.mapped_to && (
                                        <span className="text-muted-foreground ml-1">
                                          → {d.mapped_to}
                                        </span>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )
                            } catch {
                              return <pre className="text-xs whitespace-pre-wrap">{selectedAlert.change_detail}</pre>
                            }
                          })()}
                        </div>
                      </div>
                    )}

                    <div className="text-xs text-muted-foreground">
                      Created: {new Date(selectedAlert.created_at).toLocaleString()}
                      {selectedAlert.resolved_at && (
                        <span className="ml-3">
                          Resolved: {new Date(selectedAlert.resolved_at).toLocaleString()}
                          {selectedAlert.resolved_by && ` by ${selectedAlert.resolved_by}`}
                        </span>
                      )}
                    </div>
                  </>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Close</AlertDialogCancel>
            {selectedAlert?.status === "OPEN" && (
              <AlertDialogAction onClick={() => {
                updateStatus(selectedAlert.id, "RESOLVED")
                setDetailOpen(false)
              }}>
                Resolve
              </AlertDialogAction>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// ---------------------------------------------------------------------------
// Badge Components
// ---------------------------------------------------------------------------

function SeverityBadge({ severity }: { severity: string }) {
  switch (severity) {
    case "BREAKING":
      return <Badge className="bg-red-500 text-white text-[10px] px-1.5 py-0 border-0">Breaking</Badge>
    case "WARNING":
      return <Badge className="bg-amber-500 text-white text-[10px] px-1.5 py-0 border-0">Warning</Badge>
    default:
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0">Info</Badge>
  }
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "OPEN":
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-red-300 text-red-600">Open</Badge>
    case "ACKNOWLEDGED":
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-amber-300 text-amber-600">Ack</Badge>
    case "RESOLVED":
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-green-300 text-green-600">Resolved</Badge>
    case "DISMISSED":
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-gray-300 text-gray-500">Dismissed</Badge>
    default:
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0">{status}</Badge>
  }
}

function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
