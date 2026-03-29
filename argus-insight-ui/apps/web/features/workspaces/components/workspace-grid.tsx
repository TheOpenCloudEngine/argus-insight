"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  CheckCircle2,
  Circle,
  Loader2,
  MoreHorizontal,
  Rocket,
  Search,
  Trash2,
  XCircle,
} from "lucide-react"
import { AgGridReact } from "ag-grid-react"
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type PaginationNumberFormatterParams,
} from "ag-grid-community"

import { Button } from "@workspace/ui/components/button"
import { Badge } from "@workspace/ui/components/badge"
import { Input } from "@workspace/ui/components/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import type { AuditLog, WorkspaceResponse } from "@/features/workspaces/types"
import {
  deleteWorkspace,
  fetchWorkspaces,
  fetchWorkspaceAuditLogs,
} from "@/features/workspaces/api"
import { authFetch } from "@/features/auth/auth-fetch"

ModuleRegistry.registerModules([AllCommunityModule])

function formatDateTime(value: string): string {
  const d = new Date(value)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function statusColor(status: string) {
  switch (status) {
    case "active":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
    case "provisioning":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 animate-pulse"
    case "deleting":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 animate-pulse"
    case "failed":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
    case "deleted":
      return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
    default:
      return ""
  }
}

function auditStepIcon(action: string) {
  switch (action) {
    case "step_completed":
      return <CheckCircle2 className="h-4 w-4 text-green-600" />
    case "step_failed":
      return <XCircle className="h-4 w-4 text-red-600" />
    case "step_started":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
    default:
      return <Circle className="h-4 w-4 text-gray-400" />
  }
}

interface WorkspaceGridProps {
  onSelect: (workspace: WorkspaceResponse) => void
  onDeleted: (workspaceId: number) => void
  refreshKey: number
  onAddWorkspace?: () => void
}

export function WorkspaceGrid({ onSelect, onDeleted, refreshKey, onAddWorkspace }: WorkspaceGridProps) {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([])
  const [loading, setLoading] = useState(true)

  // Search
  const [searchInput, setSearchInput] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")

  // Deploy pipeline dialog state
  interface PipelineItem { id: number; name: string; display_name: string; version: number; plugins: { plugin_name: string }[] }
  const [deployOpen, setDeployOpen] = useState(false)
  const [deployTarget, setDeployTarget] = useState<WorkspaceResponse | null>(null)
  const [deployPipelines, setDeployPipelines] = useState<PipelineItem[]>([])
  const [selectedPipelineId, setSelectedPipelineId] = useState<string>("")
  const [deploying, setDeploying] = useState(false)
  const [deployPhase, setDeployPhase] = useState<"select" | "progress" | "done" | "error">("select")
  const [deploySteps, setDeploySteps] = useState<AuditLog[]>([])
  const [deployError, setDeployError] = useState<string | null>(null)
  const deployPollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Delete dialog state
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmTarget, setConfirmTarget] = useState<WorkspaceResponse | null>(null)
  const [deletePhase, setDeletePhase] = useState<"confirm" | "progress" | "done" | "error">("confirm")
  const [deleteSteps, setDeleteSteps] = useState<AuditLog[]>([])
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadWorkspaces = useCallback(async (showLoading = true, search?: string) => {
    try {
      if (showLoading) setLoading(true)
      const data = await fetchWorkspaces(1, 100, undefined, search || undefined)
      data.items = data.items.filter((w) => w.status !== "deleted")
      setWorkspaces(data.items)
    } catch {
      setWorkspaces([])
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadWorkspaces(true, appliedSearch)
  }, [loadWorkspaces, refreshKey, appliedSearch])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
      if (deployPollingRef.current) clearInterval(deployPollingRef.current)
    }
  }, [])

  // --- Deploy Pipeline ---
  const openDeployDialog = useCallback(async (ws: WorkspaceResponse) => {
    setDeployTarget(ws)
    setDeployPhase("select")
    setSelectedPipelineId("")
    setDeploySteps([])
    setDeployError(null)
    setDeploying(false)
    setDeployOpen(true)
    // Load pipelines
    try {
      const res = await authFetch("/api/v1/plugins/pipelines")
      if (res.ok) {
        const data = await res.json()
        setDeployPipelines(data.items ?? [])
      }
    } catch { /* ignore */ }
  }, [])

  const handleDeploy = useCallback(async () => {
    if (!deployTarget || !selectedPipelineId) return
    setDeploying(true)
    setDeployPhase("progress")
    setDeploySteps([])
    setDeployError(null)

    try {
      // Call a deploy API — reuse workspace provisioning with pipeline_ids
      const res = await authFetch(`/api/v1/workspace/workspaces/${deployTarget.id}/deploy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pipeline_id: parseInt(selectedPipelineId) }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Deploy failed: ${res.status}`)
      }
    } catch (e) {
      setDeployError(e instanceof Error ? e.message : "Deploy failed")
      setDeployPhase("error")
      setDeploying(false)
      return
    }

    // Poll audit logs for workflow progress
    const wsId = deployTarget.id
    deployPollingRef.current = setInterval(async () => {
      try {
        const data = await fetchWorkspaceAuditLogs(wsId, 1, 50)
        const stepLogs = data.items.filter((l) =>
          ["step_started", "step_completed", "step_failed"].includes(l.action) &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        setDeploySteps(stepLogs.reverse())

        const completed = data.items.find((l) =>
          l.action === "workflow_completed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        const failed = data.items.find((l) =>
          l.action === "workflow_failed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        if (completed) {
          if (deployPollingRef.current) clearInterval(deployPollingRef.current)
          deployPollingRef.current = null
          setDeployPhase("done")
          setDeploying(false)
          await loadWorkspaces(false, appliedSearch)
        } else if (failed) {
          if (deployPollingRef.current) clearInterval(deployPollingRef.current)
          deployPollingRef.current = null
          setDeployError(String((failed.detail as Record<string, unknown>)?.error || "Deployment failed"))
          setDeployPhase("error")
          setDeploying(false)
        }
      } catch { /* ignore */ }
    }, 2000)
  }, [deployTarget, selectedPipelineId, loadWorkspaces, appliedSearch])

  const closeDeployDialog = useCallback(() => {
    if (deployPollingRef.current) {
      clearInterval(deployPollingRef.current)
      deployPollingRef.current = null
    }
    setDeployOpen(false)
    setDeployTarget(null)
  }, [])

  const openDeleteDialog = useCallback((ws: WorkspaceResponse) => {
    setConfirmTarget(ws)
    setDeletePhase("confirm")
    setDeleteSteps([])
    setDeleteError(null)
    setConfirmOpen(true)
  }, [])

  const handleDelete = useCallback(async () => {
    if (!confirmTarget) return
    setDeletePhase("progress")
    setDeleteSteps([])
    setDeleteError(null)

    try {
      await deleteWorkspace(confirmTarget.id, true)
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Delete request failed")
      setDeletePhase("error")
      return
    }

    // Poll audit logs for delete workflow progress
    const wsId = confirmTarget.id
    pollingRef.current = setInterval(async () => {
      try {
        const data = await fetchWorkspaceAuditLogs(wsId, 1, 50)
        const stepLogs = data.items.filter((l) =>
          ["step_started", "step_completed", "step_failed"].includes(l.action) &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-delete"
        )
        setDeleteSteps(stepLogs.reverse())

        const completed = data.items.find((l) =>
          l.action === "workflow_completed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-delete"
        )
        const failed = data.items.find((l) =>
          l.action === "workflow_failed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-delete"
        )
        if (completed) {
          if (pollingRef.current) clearInterval(pollingRef.current)
          pollingRef.current = null
          setDeletePhase("done")
          onDeleted(wsId)
          await loadWorkspaces(false, appliedSearch)
        } else if (failed) {
          if (pollingRef.current) clearInterval(pollingRef.current)
          pollingRef.current = null
          setDeleteError(String((failed.detail as Record<string, unknown>)?.error || "Deletion failed"))
          setDeletePhase("error")
          await loadWorkspaces(false, appliedSearch)
        }
      } catch { /* ignore */ }
    }, 2000)
  }, [confirmTarget, onDeleted, loadWorkspaces])

  const closeDeleteDialog = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    setConfirmOpen(false)
    setConfirmTarget(null)
    if (deletePhase === "done" || deletePhase === "error") {
      loadWorkspaces(false, appliedSearch)
    }
  }, [deletePhase, loadWorkspaces, appliedSearch])

  const columnDefs = useMemo<ColDef<WorkspaceResponse>[]>(
    () => [
      {
        headerName: "Name",
        field: "display_name",
        flex: 1,
        minWidth: 150,
      },
      {
        headerName: "Description",
        field: "description",
        flex: 1.5,
        minWidth: 200,
      },
      {
        headerName: "Owner",
        field: "created_by_username",
        width: 120,
        valueGetter: (params) =>
          params.data?.created_by_username || `User #${params.data?.created_by}`,
      },
      {
        headerName: "Status",
        field: "status",
        width: 130,
        cellRenderer: (params: { value: string }) => (
          <Badge className={`${statusColor(params.value)} hover:${statusColor(params.value)}`}>
            {params.value}
          </Badge>
        ),
      },
      {
        headerName: "Created",
        field: "created_at",
        width: 160,
        valueFormatter: (params) =>
          params.value ? formatDateTime(params.value) : "",
      },
      {
        headerName: "Updated",
        field: "updated_at",
        width: 160,
        valueFormatter: (params) =>
          params.value ? formatDateTime(params.value) : "",
      },
      {
        headerName: "Action",
        width: 80,
        sortable: false,
        filter: false,
        cellRenderer: (params: { data: WorkspaceResponse }) => (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {(() => {
                const busy = params.data.status === "provisioning" || params.data.status === "deleting"
                return (
                  <>
                    <DropdownMenuItem
                      disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation()
                        if (!busy) openDeployDialog(params.data)
                      }}
                    >
                      <Rocket className="h-4 w-4 mr-2" />
                      {params.data.status === "provisioning" ? "Deploying..." : "Deploy Pipeline"}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive"
                      disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation()
                        if (!busy) openDeleteDialog(params.data)
                      }}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      {params.data.status === "deleting" ? "Deleting..." : "Delete"}
                    </DropdownMenuItem>
                  </>
                )
              })()}
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      },
    ],
    [openDeleteDialog, openDeployDialog],
  )

  return (
    <>
      <div className="flex items-center justify-between mb-0">
        <div className="relative w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search workspaces and press Enter..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                setAppliedSearch(searchInput.trim())
              }
            }}
            className="pl-9 h-9"
          />
        </div>
        {onAddWorkspace && (
          <Button onClick={onAddWorkspace}>
            Add Workspace
          </Button>
        )}
      </div>
      <div className="ag-theme-alpine" style={{ width: "100%" }}>
        <style>{`
          .ag-theme-alpine {
            --ag-font-family: 'Roboto Condensed', Roboto, sans-serif;
            --ag-font-size: var(--text-sm);
          }
        `}</style>
        <AgGridReact<WorkspaceResponse>
          rowData={workspaces}
          columnDefs={columnDefs}
          loading={loading}
          rowSelection="single"
          onRowClicked={(event) => {
            if (event.data) onSelect(event.data)
          }}
          getRowId={(params) => String(params.data.id)}
          domLayout="autoHeight"
          headerHeight={36}
          rowHeight={40}
          pagination={true}
          paginationPageSize={10}
          paginationPageSizeSelector={[10, 20, 50]}
          paginationNumberFormatter={(params: PaginationNumberFormatterParams) =>
            params.value.toLocaleString()
          }
          overlayNoRowsTemplate="No workspaces found."
        />
      </div>

      {/* Delete Progress Dialog */}
      <Dialog open={confirmOpen} onOpenChange={(open) => { if (!open) closeDeleteDialog() }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Workspace</DialogTitle>
            <DialogDescription>
              {deletePhase === "confirm" && "This will tear down all provisioned resources."}
              {deletePhase === "progress" && "Deleting workspace resources..."}
              {deletePhase === "done" && "Workspace deleted successfully."}
              {deletePhase === "error" && "Deletion encountered an error."}
            </DialogDescription>
          </DialogHeader>

          {confirmTarget && (
            <p className="text-sm font-medium">
              {confirmTarget.display_name}
              <span className="text-muted-foreground ml-1">({confirmTarget.name})</span>
            </p>
          )}

          {/* Step progress */}
          {(deletePhase === "progress" || deletePhase === "done" || deletePhase === "error") && (
            <div className="space-y-2 py-2">
              {deleteSteps.length === 0 && deletePhase === "progress" && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Initializing deletion...
                </div>
              )}
              {deleteSteps.map((log) => {
                const d = log.detail as Record<string, unknown> | null
                return (
                  <div key={log.id} className="flex items-center gap-3 text-sm">
                    {auditStepIcon(log.action)}
                    <span className="flex-1 font-medium">{String(d?.step_name ?? log.action)}</span>
                    <span className="text-xs text-muted-foreground">{log.action.replace("step_", "")}</span>
                    {log.action === "step_failed" && d?.error && (
                      <span className="text-xs text-red-600 truncate max-w-[150px]" title={String(d.error)}>
                        {String(d.error)}
                      </span>
                    )}
                  </div>
                )
              })}

              {deletePhase === "done" && (
                <div className="mt-2 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-2 text-sm">
                  All resources have been torn down.
                </div>
              )}

              {deletePhase === "error" && deleteError && (
                <div className="mt-2 rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm">
                  {deleteError}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2">
            {deletePhase === "confirm" && (
              <>
                <Button variant="outline" onClick={closeDeleteDialog}>
                  Cancel
                </Button>
                <Button variant="destructive" onClick={handleDelete}>
                  <Trash2 className="h-4 w-4 mr-1.5" />
                  Delete
                </Button>
              </>
            )}
            {deletePhase === "progress" && (
              <Button variant="outline" disabled>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                Deleting...
              </Button>
            )}
            {(deletePhase === "done" || deletePhase === "error") && (
              <Button onClick={closeDeleteDialog}>
                Close
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Deploy Pipeline Dialog */}
      <Dialog open={deployOpen} onOpenChange={(open) => { if (!open) closeDeployDialog() }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {deployPhase === "select" && "Deploy Pipeline"}
              {deployPhase === "progress" && "Deploying Pipeline"}
              {deployPhase === "done" && "Deployment Complete"}
              {deployPhase === "error" && "Deployment Failed"}
            </DialogTitle>
            <DialogDescription>
              {deployPhase === "select" && `Select a pipeline to deploy to "${deployTarget?.display_name}".`}
              {deployPhase === "progress" && "Provisioning resources..."}
              {deployPhase === "done" && "Pipeline deployed successfully."}
              {deployPhase === "error" && "Deployment encountered an error."}
            </DialogDescription>
          </DialogHeader>

          {deployPhase === "select" && (
            <div className="space-y-3 py-2">
              <Select value={selectedPipelineId} onValueChange={setSelectedPipelineId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a pipeline..." />
                </SelectTrigger>
                <SelectContent>
                  {deployPipelines.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.display_name} (v{p.version}) — {p.plugins.length} plugins
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {(deployPhase === "progress" || deployPhase === "done" || deployPhase === "error") && (
            <div className="space-y-2 py-2">
              {deploySteps.length === 0 && deployPhase === "progress" && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" /> Initializing...
                </div>
              )}
              {deploySteps.map((log) => {
                const d = log.detail as Record<string, unknown> | null
                return (
                  <div key={log.id} className="flex items-center gap-3 text-sm">
                    {auditStepIcon(log.action)}
                    <span className="flex-1 font-medium">{String(d?.step_name ?? log.action)}</span>
                    <span className="text-xs text-muted-foreground">{log.action.replace("step_", "")}</span>
                  </div>
                )
              })}
              {deployPhase === "done" && (
                <div className="mt-2 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-2 text-sm">
                  All resources have been provisioned.
                </div>
              )}
              {deployPhase === "error" && deployError && (
                <div className="mt-2 rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm">
                  {deployError}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2">
            {deployPhase === "select" && (
              <Button onClick={handleDeploy} disabled={!selectedPipelineId}>
                <Rocket className="h-4 w-4 mr-1.5" />
                Deploy
              </Button>
            )}
            {deployPhase === "progress" && (
              <Button variant="outline" disabled>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                Deploying...
              </Button>
            )}
            {(deployPhase === "done" || deployPhase === "error") && (
              <Button onClick={closeDeployDialog}>Close</Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
