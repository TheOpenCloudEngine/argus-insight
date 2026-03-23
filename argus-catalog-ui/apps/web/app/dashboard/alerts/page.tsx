"use client"

import { useCallback, useEffect, useState } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { Card, CardContent } from "@workspace/ui/components/card"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { Switch } from "@workspace/ui/components/switch"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@workspace/ui/components/select"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@workspace/ui/components/table"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { Bell, Check, Eye, X, Plus, Pencil, Trash2, Database, Tag, GitBranch, Server, Globe } from "lucide-react"
import { toast } from "sonner"
import { authFetch } from "@/features/auth/auth-fetch"
import { RuleCreateDialog } from "@/features/alerts/components/rule-create-dialog"

const BASE = "/api/v1/alerts"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Alert = {
  id: number; alert_type: string; severity: string
  source_dataset_id: number; source_dataset_name: string | null; source_platform_type: string | null
  affected_dataset_id: number | null; affected_dataset_name: string | null; affected_platform_type: string | null
  lineage_id: number | null; rule_id: number | null; rule_name: string | null
  change_summary: string; change_detail: string | null
  status: string; resolved_by: string | null; resolved_at: string | null; created_at: string
}

type PaginatedAlerts = { items: Alert[]; total: number; page: number; page_size: number }

type AlertRule = {
  id: number; rule_name: string; description: string | null
  scope_type: string; scope_id: number | null; scope_name: string | null
  trigger_type: string; trigger_config: string
  severity_override: string | null; channels: string
  notify_owners: string; webhook_url: string | null; subscribers: string | null
  is_active: string; created_by: string | null
  created_at: string; updated_at: string; alert_count: number
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AlertsPage() {
  const [tab, setTab] = useState("alerts")
  const [ruleDialogOpen, setRuleDialogOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null)

  return (
    <>
      <DashboardHeader title="Alerts" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Tabs value={tab} onValueChange={setTab}>
          <div className="flex items-center justify-between">
            <TabsList>
              <TabsTrigger value="alerts">Alerts</TabsTrigger>
              <TabsTrigger value="rules">Rules</TabsTrigger>
            </TabsList>
            {tab === "rules" && (
              <Button size="sm" onClick={() => { setEditingRule(null); setRuleDialogOpen(true) }} className="gap-1.5">
                <Plus className="h-3.5 w-3.5" />
                Add Rule
              </Button>
            )}
          </div>

          <TabsContent value="alerts" className="mt-4">
            <AlertsTab />
          </TabsContent>
          <TabsContent value="rules" className="mt-4">
            <RulesTab onAddRule={() => setRuleDialogOpen(true)} onEditRule={(rule) => { setEditingRule(rule); setRuleDialogOpen(true) }} />
          </TabsContent>
        </Tabs>
      </div>

      <RuleCreateDialog
        open={ruleDialogOpen}
        onOpenChange={(o) => { setRuleDialogOpen(o); if (!o) setEditingRule(null) }}
        onCreated={() => setTab("rules")}
        editRule={editingRule}
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// Alerts Tab
// ---------------------------------------------------------------------------

function AlertsTab() {
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
    } catch { /* */ } finally { setLoading(false) }
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
      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(1) }}>
          <SelectTrigger className="w-40 h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="OPEN">Open</SelectItem>
            <SelectItem value="ACKNOWLEDGED">Acknowledged</SelectItem>
            <SelectItem value="RESOLVED">Resolved</SelectItem>
            <SelectItem value="DISMISSED">Dismissed</SelectItem>
          </SelectContent>
        </Select>
        <Select value={severityFilter} onValueChange={v => { setSeverityFilter(v); setPage(1) }}>
          <SelectTrigger className="w-40 h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Severity</SelectItem>
            <SelectItem value="BREAKING">Breaking</SelectItem>
            <SelectItem value="WARNING">Warning</SelectItem>
            <SelectItem value="INFO">Info</SelectItem>
          </SelectContent>
        </Select>
        <span className="ml-auto text-sm text-muted-foreground">{data ? `${data.total} alert(s)` : ""}</span>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">Severity</TableHead>
                <TableHead>Change</TableHead>
                <TableHead className="w-44">Source</TableHead>
                <TableHead className="w-44">Affected</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-28">Time</TableHead>
                <TableHead className="w-24">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">Loading...</TableCell></TableRow>
              ) : !data || data.items.length === 0 ? (
                <TableRow><TableCell colSpan={7} className="text-center py-12">
                  <Bell className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No alerts found</p>
                </TableCell></TableRow>
              ) : data.items.map(alert => (
                <TableRow key={alert.id} className="cursor-pointer hover:bg-muted/50"
                  onClick={() => { setSelectedAlert(alert); setDetailOpen(true) }}>
                  <TableCell><SeverityBadge severity={alert.severity} /></TableCell>
                  <TableCell>
                    <p className="text-sm truncate max-w-sm">{alert.change_summary}</p>
                    {alert.rule_name && (
                      <p className="text-sm text-muted-foreground mt-0.5">Rule: {alert.rule_name}</p>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-sm">
                      <span className="text-muted-foreground">{alert.source_platform_type}</span>
                      <p className="font-medium truncate">{alert.source_dataset_name}</p>
                    </div>
                  </TableCell>
                  <TableCell>
                    {alert.affected_dataset_name ? (
                      <div className="text-sm">
                        <span className="text-muted-foreground">{alert.affected_platform_type}</span>
                        <p className="font-medium truncate">{alert.affected_dataset_name}</p>
                      </div>
                    ) : <span className="text-sm text-muted-foreground">-</span>}
                  </TableCell>
                  <TableCell><StatusBadge status={alert.status} /></TableCell>
                  <TableCell><span className="text-sm text-muted-foreground">{formatTimeAgo(alert.created_at)}</span></TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                      {alert.status === "OPEN" && (
                        <>
                          <Button variant="ghost" size="icon" className="h-7 w-7" title="Acknowledge" onClick={() => updateStatus(alert.id, "ACKNOWLEDGED")}><Eye className="h-3.5 w-3.5" /></Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" title="Resolve" onClick={() => updateStatus(alert.id, "RESOLVED")}><Check className="h-3.5 w-3.5" /></Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" title="Dismiss" onClick={() => updateStatus(alert.id, "DISMISSED")}><X className="h-3.5 w-3.5" /></Button>
                        </>
                      )}
                      {alert.status === "ACKNOWLEDGED" && (
                        <Button variant="ghost" size="icon" className="h-7 w-7" title="Resolve" onClick={() => updateStatus(alert.id, "RESOLVED")}><Check className="h-3.5 w-3.5" /></Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
        </div>
      )}

      {/* Detail dialog */}
      <AlertDialog open={detailOpen} onOpenChange={setDetailOpen}>
        <AlertDialogContent className="max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              Alert Detail {selectedAlert && <SeverityBadge severity={selectedAlert.severity} />}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 pt-2">
                {selectedAlert && (
                  <>
                    <div>
                      <span className="text-sm text-muted-foreground">Change</span>
                      <p className="text-sm font-medium">{selectedAlert.change_summary}</p>
                    </div>
                    {selectedAlert.rule_name && (
                      <div>
                        <span className="text-sm text-muted-foreground">Rule</span>
                        <p className="text-sm">{selectedAlert.rule_name}</p>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <span className="text-sm text-muted-foreground">Source</span>
                        <p className="text-sm">{selectedAlert.source_platform_type}.{selectedAlert.source_dataset_name}</p>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Affected</span>
                        <p className="text-sm">{selectedAlert.affected_dataset_name ? `${selectedAlert.affected_platform_type}.${selectedAlert.affected_dataset_name}` : "-"}</p>
                      </div>
                    </div>
                    {selectedAlert.change_detail && (
                      <div>
                        <span className="text-sm text-muted-foreground">Detail</span>
                        <div className="mt-1 max-h-48 overflow-y-auto">
                          {(() => {
                            try {
                              const details = JSON.parse(selectedAlert.change_detail!)
                              return <div className="space-y-1.5">{details.map((d: Record<string, string>, i: number) => (
                                <div key={i} className="text-sm bg-muted/50 rounded px-3 py-2">
                                  <span className="font-medium">{d.changed_column || d.field}</span>
                                  <span className="text-muted-foreground ml-1">({d.change_type || d.type})</span>
                                  {d.mapped_to && <span className="text-muted-foreground ml-1">→ {d.mapped_to}</span>}
                                </div>
                              ))}</div>
                            } catch { return <pre className="text-sm whitespace-pre-wrap">{selectedAlert.change_detail}</pre> }
                          })()}
                        </div>
                      </div>
                    )}
                    <div className="text-sm text-muted-foreground">
                      Created: {new Date(selectedAlert.created_at).toLocaleString()}
                    </div>
                  </>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Close</AlertDialogCancel>
            {selectedAlert?.status === "OPEN" && (
              <AlertDialogAction onClick={() => { updateStatus(selectedAlert.id, "RESOLVED"); setDetailOpen(false) }}>Resolve</AlertDialogAction>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// ---------------------------------------------------------------------------
// Rules Tab
// ---------------------------------------------------------------------------

function RulesTab({ onAddRule, onEditRule }: { onAddRule: () => void; onEditRule: (rule: AlertRule) => void }) {
  const [rules, setRules] = useState<AlertRule[]>([])
  const [loading, setLoading] = useState(true)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [deleteTargetRule, setDeleteTargetRule] = useState<AlertRule | null>(null)

  const fetchRules = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await authFetch(`${BASE}/rules`)
      if (resp.ok) setRules(await resp.json())
    } catch { /* */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchRules() }, [fetchRules])

  const toggleActive = async (rule: AlertRule) => {
    const newActive = rule.is_active === "true" ? "false" : "true"
    await authFetch(`${BASE}/rules/${rule.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: newActive }),
    })
    fetchRules()
  }

  const handleDeleteClick = (rule: AlertRule) => {
    if (rule.is_active === "true") {
      toast.error("Cannot delete an active rule. Please deactivate it first.")
      return
    }
    setDeleteTargetRule(rule)
    setDeleteConfirmOpen(true)
  }

  const confirmDelete = async () => {
    if (!deleteTargetRule) return
    await authFetch(`${BASE}/rules/${deleteTargetRule.id}`, { method: "DELETE" })
    setDeleteConfirmOpen(false)
    setDeleteTargetRule(null)
    fetchRules()
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground text-center py-8">Loading rules...</p>
  }

  if (rules.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-4">
          <Bell className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">No alert rules defined yet.</p>
          <Button size="sm" onClick={onAddRule} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" /> Create First Rule
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {rules.map(rule => (
        <Card key={rule.id} className={rule.is_active === "false" ? "opacity-60" : ""}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                {/* Header */}
                <div className="flex items-center gap-2 mb-2">
                  {rule.severity_override ? (
                    <SeverityBadge severity={rule.severity_override} />
                  ) : (
                    <Badge variant="outline" className="text-sm px-1.5 py-0">Auto</Badge>
                  )}
                  <span className="font-medium text-sm">{rule.rule_name}</span>
                </div>

                {/* Scope */}
                <div className="flex items-center gap-2 mb-2">
                  <ScopeIcon type={rule.scope_type} />
                  <span className="text-sm text-muted-foreground">
                    {rule.scope_type}: {rule.scope_name || "All"}
                  </span>
                </div>

                {/* Trigger + Channels */}
                <div className="flex items-center gap-4 text-smtext-muted-foreground">
                  <span>Trigger: <span className="text-foreground">{rule.trigger_type}</span></span>
                  <span>Channels: <span className="text-foreground">{rule.channels}</span></span>
                  {rule.subscribers && (
                    <span>Subscribers: <span className="text-foreground">{rule.subscribers.split(",").length}명</span></span>
                  )}
                  <span>Alerts: <span className="text-foreground">{rule.alert_count}</span></span>
                </div>

                {rule.description && (
                  <p className="text-sm text-muted-foreground mt-2">{rule.description}</p>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 ml-4">
                <Switch
                  checked={rule.is_active === "true"}
                  onCheckedChange={() => toggleActive(rule)}
                />
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEditRule(rule)}>
                  <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleDeleteClick(rule)}>
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}

      {/* Delete confirmation dialog */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Rule</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the rule &quot;{deleteTargetRule?.rule_name}&quot;? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ScopeIcon({ type }: { type: string }) {
  const cls = "h-3.5 w-3.5 text-muted-foreground"
  switch (type) {
    case "DATASET": return <Database className={cls} />
    case "TAG": return <Tag className={cls} />
    case "LINEAGE": return <GitBranch className={cls} />
    case "PLATFORM": return <Server className={cls} />
    default: return <Globe className={cls} />
  }
}

function SeverityBadge({ severity }: { severity: string }) {
  if (severity === "BREAKING") return <Badge className="bg-red-500 text-white text-sm px-1.5 py-0 border-0">Breaking</Badge>
  if (severity === "WARNING") return <Badge className="bg-amber-500 text-white text-sm px-1.5 py-0 border-0">Warning</Badge>
  return <Badge variant="outline" className="text-sm px-1.5 py-0">Info</Badge>
}

function StatusBadge({ status }: { status: string }) {
  if (status === "OPEN") return <Badge variant="outline" className="text-sm px-1.5 py-0 border-red-300 text-red-600">Open</Badge>
  if (status === "ACKNOWLEDGED") return <Badge variant="outline" className="text-sm px-1.5 py-0 border-amber-300 text-amber-600">Ack</Badge>
  if (status === "RESOLVED") return <Badge variant="outline" className="text-sm px-1.5 py-0 border-green-300 text-green-600">Resolved</Badge>
  if (status === "DISMISSED") return <Badge variant="outline" className="text-sm px-1.5 py-0 border-gray-300 text-gray-500">Dismissed</Badge>
  return <Badge variant="outline" className="text-sm px-1.5 py-0">{status}</Badge>
}

function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}
