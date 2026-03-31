"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { ArrowDown, ArrowUp, CheckCircle2, Circle, Loader2, Plus, Trash2, XCircle } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Separator } from "@workspace/ui/components/separator"
import { DashboardHeader } from "@/components/dashboard-header"
import { useAuth } from "@/features/auth"

import type { AuditLog, WorkspaceResponse } from "@/features/workspaces/types"
import { fetchWorkspaceAuditLogs } from "@/features/workspaces/api"
import { WorkspaceGrid } from "@/features/workspaces/components/workspace-grid"
import { WorkspaceDetail } from "@/features/workspaces/components/workspace-detail"
import { authFetch } from "@/features/auth/auth-fetch"

// Minimal pipeline type for selection
interface PipelineItem {
  id: number
  name: string
  display_name: string
  description: string | null
  version: number
  plugins: { plugin_name: string; selected_version: string | null }[]
}

function auditStepIcon(action: string) {
  switch (action) {
    case "step_completed": return <CheckCircle2 className="h-4 w-4 text-green-600" />
    case "step_failed": return <XCircle className="h-4 w-4 text-red-600" />
    case "step_started": return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
    default: return <Circle className="h-4 w-4 text-gray-400" />
  }
}

export default function WorkspacesPage() {
  const { user } = useAuth()
  const [selectedWorkspace, setSelectedWorkspace] = useState<WorkspaceResponse | null>(null)
  const [gridRefreshKey, setGridRefreshKey] = useState(0)

  // Add Workspace dialog
  const [addOpen, setAddOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [createPhase, setCreatePhase] = useState<"form" | "progress" | "done" | "error">("form")
  const [createSteps, setCreateSteps] = useState<AuditLog[]>([])
  const [createdWsId, setCreatedWsId] = useState<number | null>(null)
  const createPollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Form fields
  const [wsName, setWsName] = useState("")
  const [wsNameError, setWsNameError] = useState<string | null>(null)
  const [wsDisplayName, setWsDisplayName] = useState("")
  const [wsDescription, setWsDescription] = useState("")
  const [wsDomain, setWsDomain] = useState("")
  const [wsNamespace, setWsNamespace] = useState("")
  const [nsPrefix, setNsPrefix] = useState("argus-ws-")

  // Name availability check
  const [checking, setChecking] = useState(false)
  const [wsNameAvailable, setWsNameAvailable] = useState<boolean | null>(null)
  const [nsAvailable, setNsAvailable] = useState<boolean | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Pipeline selection (ordered array)
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
  const [selectedPipelines, setSelectedPipelines] = useState<PipelineItem[]>([])
  const [loadingPipelines, setLoadingPipelines] = useState(false)

  // Users for admin selection
  const [users, setUsers] = useState<{ id: number; username: string }[]>([])
  const [adminUserId, setAdminUserId] = useState<string>("")

  // Name validation + debounced availability check
  const handleNameChange = useCallback((value: string) => {
    // Only allow lowercase letters, numbers, and underscore
    const cleaned = value.replace(/[^a-z0-9_]/g, "")
    setWsName(cleaned)
    setWsNamespace(`${nsPrefix}${cleaned}`)
    setWsNameAvailable(null)
    setNsAvailable(null)

    if (cleaned.length < 2) {
      setWsNameError(cleaned.length > 0 ? "Name must be at least 2 characters" : null)
      return
    }
    if (cleaned.length >= 12) {
      setWsNameError("Name must be less than 12 characters")
      return
    }
    if (!/^[a-z][a-z0-9_]*$/.test(cleaned)) {
      setWsNameError("Must start with a lowercase letter")
      return
    }
    setWsNameError(null)

    // Debounce: check after 2 seconds
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setChecking(true)
      try {
        const [wsRes, nsRes] = await Promise.all([
          authFetch(`/api/v1/workspace/workspaces/check?name=${cleaned}`),
          authFetch(`/api/v1/settings/k8s/namespace/${nsPrefix}${cleaned}`),
        ])
        if (wsRes.ok) {
          const wsData = await wsRes.json()
          setWsNameAvailable(!wsData.exists)
        }
        if (nsRes.ok) {
          const nsData = await nsRes.json()
          setNsAvailable(!nsData.exists)
        }
      } catch {
        // ignore
      } finally {
        setChecking(false)
      }
    }, 2000)
  }, [nsPrefix])

  // Cleanup debounce and polling on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      if (createPollingRef.current) clearInterval(createPollingRef.current)
    }
  }, [])

  const nameValid = wsName.length >= 2 && !wsNameError && wsNameAvailable === true
  const canCreate = nameValid && wsDisplayName.trim().length > 0 && wsDomain.trim().length > 0 && !!adminUserId

  const handleSelect = useCallback((workspace: WorkspaceResponse) => {
    setSelectedWorkspace(workspace)
  }, [])

  const handleRefresh = useCallback(() => {
    setGridRefreshKey((k) => k + 1)
  }, [])

  const handleDeleted = useCallback((workspaceId: number) => {
    if (selectedWorkspace && selectedWorkspace.id === workspaceId) {
      setSelectedWorkspace(null)
    }
  }, [selectedWorkspace])

  // Load domain from settings
  const loadDomain = useCallback(async () => {
    try {
      const res = await authFetch("/api/v1/settings/configuration")
      if (res.ok) {
        const data = await res.json()
        const domainCat = data.categories?.find((c: { category: string }) => c.category === "domain")
        if (domainCat?.items?.domain_name) {
          setWsDomain(domainCat.items.domain_name)
        }
      }
    } catch { /* ignore */ }
  }, [])

  // Load pipelines and users when dialog opens
  const openAddDialog = useCallback(async () => {
    setAddOpen(true)
    setAddError(null)
    setWsName("")
    setWsNameError(null)
    setWsDisplayName("")
    setWsDescription("")
    setWsNamespace("")
    setWsNameAvailable(null)
    setNsAvailable(null)
    setSelectedPipelines([])
    setCreating(false)
    setCreatePhase("form")
    setCreateSteps([])
    setCreatedWsId(null)

    await loadDomain()

    // Load K8s config for namespace prefix
    try {
      const k8sRes = await authFetch("/api/v1/settings/k8s")
      if (k8sRes.ok) {
        const k8sData = await k8sRes.json()
        if (k8sData.namespace_prefix) setNsPrefix(k8sData.namespace_prefix)
      }
    } catch { /* ignore */ }

    // Load pipelines
    setLoadingPipelines(true)
    try {
      const res = await authFetch("/api/v1/plugins/pipelines")
      if (res.ok) {
        const data = await res.json()
        setPipelines(data.items ?? [])
      }
    } catch { /* ignore */ }
    setLoadingPipelines(false)

    // Load users
    try {
      const res = await authFetch("/api/v1/usermgr/users?page_size=100")
      if (res.ok) {
        const data = await res.json()
        const userList = (data.items ?? []).map((u: { id: number; username: string }) => ({
          id: u.id,
          username: u.username,
        }))
        setUsers(userList)
        // Default to current user
        if (user) {
          const me = userList.find((u: { username: string }) => u.username === user.username)
          if (me) setAdminUserId(String(me.id))
        }
      }
    } catch { /* ignore */ }
  }, [loadDomain, user])

  const togglePipeline = (pipeline: PipelineItem) => {
    setSelectedPipelines((prev) => {
      const exists = prev.find((p) => p.id === pipeline.id)
      if (exists) return prev.filter((p) => p.id !== pipeline.id)
      return [...prev, pipeline]
    })
  }

  const movePipelineUp = (index: number) => {
    if (index === 0) return
    setSelectedPipelines((prev) => {
      const next = [...prev]
      ;[next[index - 1], next[index]] = [next[index]!, next[index - 1]!]
      return next
    })
  }

  const movePipelineDown = (index: number) => {
    setSelectedPipelines((prev) => {
      if (index >= prev.length - 1) return prev
      const next = [...prev]
      ;[next[index], next[index + 1]] = [next[index + 1]!, next[index]!]
      return next
    })
  }

  const removePipeline = (index: number) => {
    setSelectedPipelines((prev) => prev.filter((_, i) => i !== index))
  }

  const handleCreate = async () => {
    if (!wsName.trim() || !wsDisplayName.trim() || !wsDomain.trim() || !adminUserId) return
    setCreating(true)
    setAddError(null)
    setCreatePhase("progress")
    setCreateSteps([])
    setCreatedWsId(null)

    let wsId: number | null = null
    try {
      const body: Record<string, unknown> = {
        name: wsName.trim(),
        display_name: wsDisplayName.trim(),
        description: wsDescription.trim() || null,
        domain: wsDomain.trim(),
        k8s_namespace: wsNamespace.trim() || undefined,
        admin_user_id: parseInt(adminUserId),
        pipeline_ids: selectedPipelines.map((p) => p.id),
      }
      const res = await authFetch("/api/v1/workspace/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Failed: ${res.status}`)
      }
      const created = await res.json()
      wsId = created.id
      setCreatedWsId(wsId)
    } catch (e) {
      setAddError(e instanceof Error ? e.message : "Failed to create workspace")
      setCreatePhase("error")
      setCreating(false)
      return
    }

    // Poll audit logs for provisioning progress (only events after polling start)
    const pollStartedAt = new Date().toISOString()
    createPollingRef.current = setInterval(async () => {
      if (!wsId) return
      try {
        const data = await fetchWorkspaceAuditLogs(wsId, 1, 50)
        const recent = data.items.filter((l) => l.created_at >= pollStartedAt)
        const stepLogs = recent.filter((l) =>
          ["step_started", "step_completed", "step_failed"].includes(l.action) &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        setCreateSteps(stepLogs.reverse())

        const completed = recent.find((l) =>
          l.action === "workflow_completed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        const failed = recent.find((l) =>
          l.action === "workflow_failed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        if (completed) {
          if (createPollingRef.current) clearInterval(createPollingRef.current)
          createPollingRef.current = null
          setCreatePhase("done")
          setCreating(false)
          setGridRefreshKey((k) => k + 1)
        } else if (failed) {
          if (createPollingRef.current) clearInterval(createPollingRef.current)
          createPollingRef.current = null
          setAddError(String((failed.detail as Record<string, unknown>)?.error || "Provisioning failed"))
          setCreatePhase("error")
          setCreating(false)
          setGridRefreshKey((k) => k + 1)
        }
      } catch { /* ignore */ }
    }, 2000)
  }

  const closeAddDialog = useCallback(() => {
    if (createPollingRef.current) {
      clearInterval(createPollingRef.current)
      createPollingRef.current = null
    }
    setAddOpen(false)
    setCreatePhase("form")
    setCreateSteps([])
    setCreating(false)
    if (createPhase === "done" || createPhase === "error") {
      setGridRefreshKey((k) => k + 1)
    }
  }, [createPhase])

  return (
    <>
      <DashboardHeader title="Workspaces" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <WorkspaceGrid
          onSelect={handleSelect}
          onDeleted={handleDeleted}
          refreshKey={gridRefreshKey}
          onAddWorkspace={openAddDialog}
        />

        {selectedWorkspace && (
          <>
            <Separator />
            <WorkspaceDetail
              workspace={selectedWorkspace}
              onRefresh={handleRefresh}
            />
          </>
        )}
      </div>

      {/* Add Workspace Dialog */}
      <Dialog open={addOpen} onOpenChange={(open) => { if (!open) closeAddDialog() }}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {createPhase === "form" && "Create Workspace"}
              {createPhase === "progress" && "Creating Workspace"}
              {createPhase === "done" && "Workspace Created"}
              {createPhase === "error" && "Workspace Creation"}
            </DialogTitle>
            <DialogDescription>
              {createPhase === "form" && "Create a new workspace and select pipelines to deploy."}
              {createPhase === "progress" && "Provisioning workspace resources..."}
              {createPhase === "done" && "Workspace has been created successfully."}
              {createPhase === "error" && "Workspace creation encountered an error."}
            </DialogDescription>
          </DialogHeader>

          {/* Progress / Done / Error view */}
          {(createPhase === "progress" || createPhase === "done" || createPhase === "error") && (
            <div className="space-y-3 py-2">
              {createSteps.length === 0 && createPhase === "progress" && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Initializing provisioning...
                </div>
              )}
              {createSteps.map((log) => {
                const d = log.detail as Record<string, unknown> | null
                return (
                  <div key={log.id} className="flex items-center gap-3 text-sm">
                    {auditStepIcon(log.action)}
                    <span className="flex-1 font-medium">{String(d?.step_name ?? log.action)}</span>
                    <span className="text-xs text-muted-foreground">{log.action.replace("step_", "")}</span>
                    {log.action === "step_failed" && d?.error && (
                      <span className="text-xs text-red-600 truncate max-w-[200px]" title={String(d.error)}>
                        {String(d.error)}
                      </span>
                    )}
                  </div>
                )
              })}
              {createPhase === "done" && (
                <div className="mt-2 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-2 text-sm">
                  All resources have been provisioned successfully.
                </div>
              )}
              {createPhase === "error" && addError && (
                <div className="mt-2 rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm">
                  {addError}
                </div>
              )}
            </div>
          )}

          {/* Form (only in form phase) */}
          {createPhase === "form" && addError && (
            <div className="rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm">
              {addError}
            </div>
          )}

          {createPhase === "form" && (
          <div className="space-y-4 py-2">
            {/* Basic Info */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Name <span className="text-destructive">*</span></Label>
                <Input
                  value={wsName}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="mlteamdev"
                />
                {wsNameError && (
                  <p className="text-xs text-destructive">{wsNameError}</p>
                )}
                {!wsNameError && wsName.length >= 2 && (
                  <div className="flex items-center gap-3 text-xs mt-1">
                    {checking ? (
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <Loader2 className="h-3 w-3 animate-spin" /> Checking...
                      </span>
                    ) : (
                      <>
                        {wsNameAvailable !== null && (
                          <span className={`flex items-center gap-1 ${wsNameAvailable ? "text-green-600" : "text-destructive"}`}>
                            {wsNameAvailable ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                            {wsNameAvailable ? "Name available" : "Name already exists"}
                          </span>
                        )}
                        {nsAvailable !== null && (
                          <span className={`flex items-center gap-1 ${nsAvailable ? "text-green-600" : "text-yellow-600"}`}>
                            {nsAvailable ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                            {nsAvailable ? "Namespace available" : "Namespace exists"}
                          </span>
                        )}
                      </>
                    )}
                  </div>
                )}
                <p className="text-xs text-muted-foreground">Lowercase letters, numbers, and _ only. Max 11 chars.</p>
              </div>
              <div className="space-y-1.5">
                <Label>Display Name <span className="text-destructive">*</span></Label>
                <Input
                  value={wsDisplayName}
                  onChange={(e) => setWsDisplayName(e.target.value)}
                  placeholder="ML Team Development"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input
                value={wsDescription}
                onChange={(e) => setWsDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Domain</Label>
                <Input
                  value={wsDomain}
                  readOnly
                  className="bg-muted"
                />
              </div>
              <div className="space-y-1.5">
                <Label>K8s Namespace</Label>
                <Input
                  value={wsNamespace}
                  readOnly
                  className="bg-muted font-mono text-sm"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Admin User <span className="text-destructive">*</span></Label>
              <Select value={adminUserId} onValueChange={setAdminUserId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select admin user" />
                </SelectTrigger>
                <SelectContent>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={String(u.id)}>
                      {u.username}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* Pipeline Selection */}
            <div className="space-y-2">
              <Label>Pipelines</Label>
              <p className="text-xs text-muted-foreground">
                Select pipelines to deploy. Use arrows to set execution order.
              </p>

              {loadingPipelines ? (
                <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading pipelines...
                </div>
              ) : pipelines.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2">
                  No pipelines available. Create one in Software Deployment first.
                </p>
              ) : (
                <div className="space-y-3">
                  {/* Available pipelines */}
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Available</p>
                    <div className="max-h-32 overflow-y-auto rounded-md border p-2 space-y-1">
                      {pipelines
                        .filter((p) => !selectedPipelines.find((s) => s.id === p.id))
                        .map((p) => (
                          <div
                            key={p.id}
                            className="flex items-center justify-between p-1.5 rounded hover:bg-muted/50 cursor-pointer"
                            onClick={() => togglePipeline(p)}
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-sm">{p.display_name}</span>
                              <span className="text-xs text-muted-foreground">v{p.version}</span>
                              <span className="text-xs text-muted-foreground">
                                ({p.plugins.length} plugins)
                              </span>
                            </div>
                            <Button variant="ghost" size="icon" className="h-6 w-6">
                              <Plus className="h-3 w-3" />
                            </Button>
                          </div>
                        ))}
                      {pipelines.filter((p) => !selectedPipelines.find((s) => s.id === p.id)).length === 0 && (
                        <p className="text-xs text-muted-foreground text-center py-1">All pipelines selected</p>
                      )}
                    </div>
                  </div>

                  {/* Selected pipelines (ordered) */}
                  {selectedPipelines.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">
                        Selected ({selectedPipelines.length}) — execution order
                      </p>
                      <div className="rounded-md border divide-y">
                        {selectedPipelines.map((p, i) => (
                          <div key={p.id} className="flex items-center gap-2 px-3 py-2">
                            <span className="text-xs text-muted-foreground font-mono w-5">
                              {i + 1}.
                            </span>
                            <div className="flex-1 min-w-0">
                              <span className="text-sm font-medium">{p.display_name}</span>
                              <span className="text-xs text-muted-foreground ml-2">
                                v{p.version} · {p.plugins.length} plugins
                              </span>
                            </div>
                            <div className="flex gap-0.5">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                disabled={i === 0}
                                onClick={() => movePipelineUp(i)}
                              >
                                <ArrowUp className="h-3 w-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                disabled={i === selectedPipelines.length - 1}
                                onClick={() => movePipelineDown(i)}
                              >
                                <ArrowDown className="h-3 w-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 text-destructive"
                                onClick={() => removePipeline(i)}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            {createPhase === "form" && (
              <>
                <Button variant="outline" onClick={closeAddDialog}>
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={creating || !canCreate}
                >
                  <Plus className="h-4 w-4 mr-1.5" />
                  Create Workspace
                </Button>
              </>
            )}
            {createPhase === "progress" && (
              <Button variant="outline" disabled>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                Provisioning...
              </Button>
            )}
            {(createPhase === "done" || createPhase === "error") && (
              <Button onClick={closeAddDialog}>
                Close
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
