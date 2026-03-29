"use client"

import { Fragment, useEffect, useState } from "react"
import {
  Database,
  ExternalLink,
  Eye,
  EyeOff,
  FolderGit2,
  Loader2,
  Plus,
  Search,
  Server,
  Shield,
  Trash2,
  UserMinus,
  UserPlus,
  Workflow,
} from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { Avatar, AvatarFallback } from "@workspace/ui/components/avatar"
import { Badge } from "@workspace/ui/components/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { Button } from "@workspace/ui/components/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import type {
  AuditLog,
  WorkspaceResponse,
  WorkspaceMember,
  WorkspaceService,
} from "@/features/workspaces/types"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { Input } from "@workspace/ui/components/input"
import {
  bulkAddWorkspaceMembers,
  deleteWorkspaceService,
  fetchWorkspaceAuditLogs,
  fetchWorkspaceMembers,
  fetchWorkspaceServices,
  removeWorkspaceMember,
} from "@/features/workspaces/api"
import { authFetch } from "@/features/auth/auth-fetch"

interface WorkspaceDetailProps {
  workspace: WorkspaceResponse
  onRefresh: () => void
}

function isUrl(value: string): boolean {
  return /^https?:\/\//.test(value)
}

function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

interface ResourceItem {
  label: string
  value: string | null
  icon: React.ReactNode
}

function ResourceCard({ label, value, icon }: ResourceItem) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        <div className="text-muted-foreground mt-0.5">{icon}</div>
        <div className="min-w-0 flex-1">
          <p className="text-muted-foreground text-xs font-medium">{label}</p>
          {value ? (
            isUrl(value) ? (
              <a
                href={value}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline dark:text-blue-400"
              >
                {value}
                <ExternalLink className="h-3 w-3 flex-shrink-0" />
              </a>
            ) : (
              <p className="text-sm font-medium">{value}</p>
            )
          ) : (
            <p className="text-muted-foreground text-sm italic">Not provisioned</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function roleBadge(role: string) {
  if (role === "WorkspaceAdmin") {
    return (
      <Badge className="bg-blue-100 text-blue-800 hover:bg-blue-100 dark:bg-blue-900 dark:text-blue-200">
        {role}
      </Badge>
    )
  }
  return (
    <Badge className="bg-gray-100 text-gray-800 hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-200">
      {role}
    </Badge>
  )
}

// ---------- Resources Tab ----------

function ResourcesTab({ workspace }: { workspace: WorkspaceResponse }) {
  const [services, setServices] = useState<WorkspaceService[]>([])
  const [loading, setLoading] = useState(true)

  const loadServices = () => {
    setLoading(true)
    fetchWorkspaceServices(workspace.id)
      .then(setServices)
      .catch(() => setServices([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchWorkspaceServices(workspace.id)
      .then((data) => { if (!cancelled) setServices(data) })
      .catch(() => { if (!cancelled) setServices([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [workspace.id])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (services.length === 0) {
    return <div className="text-muted-foreground py-12 text-center text-sm">No services deployed</div>
  }

  const iconClass = "h-5 w-5"
  const serviceIcon = (name: string) => {
    if (name.includes("gitlab")) return <FolderGit2 className={iconClass} />
    if (name.includes("minio")) return <Database className={iconClass} />
    if (name.includes("airflow")) return <Workflow className={iconClass} />
    if (name.includes("mlflow")) return <Server className={iconClass} />
    if (name.includes("kserve")) return <Server className={iconClass} />
    return <Server className={iconClass} />
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {services.map((svc) => (
        <ServiceCard
          key={svc.id}
          svc={svc}
          icon={serviceIcon(svc.plugin_name)}
          workspaceName={workspace.name}
          workspaceId={workspace.id}
          onDeleted={loadServices}
        />
      ))}
    </div>
  )
}

function ServiceCard({
  svc, icon, workspaceName, workspaceId, onDeleted,
}: {
  svc: WorkspaceService
  icon: React.ReactNode
  workspaceName: string
  workspaceId: number
  onDeleted: () => void
}) {
  const NON_DELETABLE = ["argus-gitlab", "argus-minio-workspace"]
  const canDelete = !NON_DELETABLE.includes(svc.plugin_name)

  const [showPassword, setShowPassword] = useState(false)
  const [showToken, setShowToken] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await deleteWorkspaceService(workspaceId, svc.id)
      setDeleteOpen(false)
      onDeleted()
    } catch { /* ignore */ }
    finally { setDeleting(false) }
  }

  return (
    <>
    <Card className="hover:border-primary/30 transition-colors">
      <CardContent className="pt-4 pb-3 space-y-2.5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {icon}
            <div>
              <p className="font-semibold text-base">{svc.display_name || svc.plugin_name}</p>
              <p className="text-xs text-muted-foreground">v{svc.version}</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge
              className={
                svc.status === "running"
                  ? "bg-green-100 text-green-800 hover:bg-green-100 text-sm"
                  : svc.status === "failed"
                    ? "bg-red-100 text-red-800 hover:bg-red-100 text-sm"
                    : "text-sm"
              }
            >
              {svc.status}
            </Badge>
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                onClick={() => setDeleteOpen(true)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>

        {/* Connection Info + Metadata */}
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 pt-2 border-t text-sm">
          {svc.endpoint && (
            <>
              <dt className="text-muted-foreground">URL</dt>
              <dd className="min-w-0">
                {isUrl(svc.endpoint) ? (
                  <button
                    className="text-blue-600 hover:underline break-all text-left cursor-pointer"
                    onClick={async (e) => {
                      e.preventDefault()
                      try {
                        // Get auth token
                        const res = await authFetch(
                          `/api/v1/workspace/workspaces/auth-launch?workspace=${workspaceName}`
                        )
                        if (!res.ok) throw new Error("Auth failed")
                        const data = await res.json()
                        // Open auth-redirect on backend directly (not via Next.js proxy)
                        // so the cookie is set with the correct domain
                        const serverHost = window.location.hostname
                        const redirectUrl = `http://${serverHost}:4500/api/v1/workspace/workspaces/auth-redirect?workspace=${workspaceName}&token=${data.token}&redirect=${encodeURIComponent(svc.endpoint!)}`
                        window.open(redirectUrl, "_blank")
                      } catch {
                        // Fallback: direct open
                        window.open(svc.endpoint!, "_blank")
                      }
                    }}
                  >
                    {svc.endpoint} <ExternalLink className="inline h-3.5 w-3.5" />
                  </button>
                ) : (
                  <span className="font-mono break-all">{svc.endpoint}</span>
                )}
              </dd>
            </>
          )}

          {svc.username && (
            <>
              <dt className="text-muted-foreground">User</dt>
              <dd className="font-mono">{svc.username}</dd>
            </>
          )}

          {svc.password && (
            <>
              <dt className="text-muted-foreground">Password</dt>
              <dd className="flex items-center gap-1.5">
                <span className="font-mono">{showPassword ? svc.password : "••••••••"}</span>
                <button type="button" className="text-muted-foreground hover:text-foreground" onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </dd>
            </>
          )}

          {svc.access_token && (
            <>
              <dt className="text-muted-foreground">Token</dt>
              <dd className="flex items-center gap-1.5">
                <span className="font-mono">{showToken ? svc.access_token : "••••••••••••"}</span>
                <button type="button" className="text-muted-foreground hover:text-foreground" onClick={() => setShowToken(!showToken)}>
                  {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </dd>
            </>
          )}

          {svc.metadata && Object.entries(svc.metadata)
            .filter(([key]) => key !== "internal_endpoint")
            .map(([key, val]) => (
              <Fragment key={key}>
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="font-mono break-all">{String(val)}</dd>
              </Fragment>
            ))}

          {svc.metadata?.internal_endpoint && (
            <>
              <dt className="text-muted-foreground">Internal</dt>
              <dd className="font-mono break-all text-muted-foreground">
                {String(svc.metadata.internal_endpoint)}
              </dd>
            </>
          )}
        </dl>
      </CardContent>
    </Card>

    {/* Delete Service Confirm Dialog */}
    <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete Resource</DialogTitle>
          <DialogDescription>
            이 리소스를 삭제하시겠습니까?
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-3 py-2">
          {icon}
          <div>
            <p className="font-medium text-sm">{svc.display_name || svc.plugin_name}</p>
            {svc.endpoint && (
              <p className="text-xs text-muted-foreground break-all">{svc.endpoint}</p>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setDeleteOpen(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4 mr-1.5" />
            )}
            Delete
          </Button>
        </div>
      </DialogContent>
    </Dialog>
    </>
  )
}

// ---------- Members Tab ----------

interface SimpleUser {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
}

function MembersTab({
  workspace,
  onRefresh,
}: {
  workspace: WorkspaceResponse
  onRefresh: () => void
}) {
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [loading, setLoading] = useState(true)
  const [removingId, setRemovingId] = useState<number | null>(null)

  // Add Members dialog
  const [addOpen, setAddOpen] = useState(false)
  const [allUsers, setAllUsers] = useState<SimpleUser[]>([])
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set())
  const [userSearch, setUserSearch] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")
  const [adding, setAdding] = useState(false)

  // Remove confirm dialog
  const [removeTarget, setRemoveTarget] = useState<WorkspaceMember | null>(null)
  const [removeConfirmOpen, setRemoveConfirmOpen] = useState(false)

  const loadMembers = () => {
    setLoading(true)
    fetchWorkspaceMembers(workspace.id)
      .then(setMembers)
      .catch(() => setMembers([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchWorkspaceMembers(workspace.id)
      .then((data) => { if (!cancelled) setMembers(data) })
      .catch(() => { if (!cancelled) setMembers([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [workspace.id])

  const openRemoveConfirm = (member: WorkspaceMember) => {
    if (member.is_owner) return
    setRemoveTarget(member)
    setRemoveConfirmOpen(true)
  }

  const handleRemoveConfirm = async () => {
    if (!removeTarget) return
    setRemovingId(removeTarget.id)
    try {
      await removeWorkspaceMember(workspace.id, removeTarget.id)
      loadMembers()
      onRefresh()
    } catch { /* ignore */ }
    finally {
      setRemovingId(null)
      setRemoveConfirmOpen(false)
      setRemoveTarget(null)
    }
  }

  const [searchLoading, setSearchLoading] = useState(false)

  const searchUsers = async (query: string) => {
    setSearchLoading(true)
    try {
      const url = query
        ? `/api/v1/usermgr/users?page_size=50&search=${encodeURIComponent(query)}`
        : "/api/v1/usermgr/users?page_size=50"
      const res = await authFetch(url)
      if (res.ok) {
        const data = await res.json()
        setAllUsers(data.items ?? [])
      }
    } catch { /* ignore */ }
    finally { setSearchLoading(false) }
  }

  const openAddDialog = async () => {
    setAddOpen(true)
    setSelectedUserIds(new Set())
    setUserSearch("")
    setAppliedSearch("")
    setAdding(false)
    setAllUsers([])
    await searchUsers("")
  }

  const handleBulkAdd = async () => {
    if (selectedUserIds.size === 0) return
    setAdding(true)
    try {
      await bulkAddWorkspaceMembers(workspace.id, Array.from(selectedUserIds))
      loadMembers()
      onRefresh()
      setAddOpen(false)
    } catch { /* ignore */ }
    finally { setAdding(false) }
  }

  const memberUserIds = new Set(members.map((m) => m.user_id))
  const availableUsers = allUsers.filter((u) => !memberUserIds.has(u.id))

  const toggleUser = (id: number) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <>
      <div className="space-y-3">
        <div className="flex justify-end">
          <Button size="sm" onClick={openAddDialog}>
            Add Members
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
            <span className="text-muted-foreground ml-2 text-sm">Loading members...</span>
          </div>
        ) : members.length === 0 ? (
          <div className="text-muted-foreground py-12 text-center text-sm">No members</div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {members.map((m) => {
              const initials = m.display_name
                ? m.display_name.split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2)
                : (m.username ?? "?").slice(0, 2).toUpperCase()
              return (
                <Tooltip key={m.id}>
                  <TooltipTrigger asChild>
                    <Card className="relative hover:border-primary/50 transition-colors">
                      {/* Delete button (non-owner only) */}
                      {!m.is_owner && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="absolute top-1.5 right-1.5 h-7 w-7 text-muted-foreground hover:text-destructive"
                          disabled={removingId === m.id}
                          onClick={() => openRemoveConfirm(m)}
                        >
                          {removingId === m.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      )}
                      <CardContent className="flex flex-col items-center pt-6 pb-4 px-3">
                        <Avatar className="h-12 w-12 mb-3">
                          <AvatarFallback className="text-sm font-medium">{initials}</AvatarFallback>
                        </Avatar>
                        <p className="font-medium" style={{ fontSize: "var(--text-sm)" }}>{m.username ?? `User #${m.user_id}`}</p>
                        <p className="text-muted-foreground mt-0.5" style={{ fontSize: "var(--text-sm)" }}>{m.display_name}</p>
                        <p className="text-muted-foreground truncate max-w-full" style={{ fontSize: "var(--text-sm)" }}>{m.email}</p>
                        {m.is_owner && (
                          <Badge className="mt-2 text-xs bg-blue-600 text-white hover:bg-blue-600">
                            <Shield className="h-3 w-3 mr-1" /> Owner
                          </Badge>
                        )}
                      </CardContent>
                    </Card>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">
                    Joined {formatDateTime(m.created_at)}
                  </TooltipContent>
                </Tooltip>
              )
            })}
          </div>
        )}
      </div>

      {/* Remove Member Confirm Dialog */}
      <Dialog open={removeConfirmOpen} onOpenChange={setRemoveConfirmOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Remove Member</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove this user from the workspace?
              They will also be removed from the GitLab repository.
            </DialogDescription>
          </DialogHeader>
          {removeTarget && (
            <div className="flex items-center gap-3 py-2">
              <Avatar className="h-10 w-10">
                <AvatarFallback className="text-sm">
                  {removeTarget.display_name
                    ? removeTarget.display_name.split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2)
                    : (removeTarget.username ?? "?").slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="font-medium text-sm">{removeTarget.username}</p>
                <p className="text-xs text-muted-foreground">{removeTarget.email}</p>
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setRemoveConfirmOpen(false)} disabled={removingId !== null}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleRemoveConfirm} disabled={removingId !== null}>
              {removingId !== null ? (
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
              ) : (
                <UserMinus className="h-4 w-4 mr-1.5" />
              )}
              Remove
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Members Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Members</DialogTitle>
            <DialogDescription>
              Select users to add to this workspace. They will be provisioned in GitLab automatically.
            </DialogDescription>
          </DialogHeader>

          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search users and press Enter..."
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  setAppliedSearch(userSearch.trim())
                  searchUsers(userSearch.trim())
                }
              }}
              className="pl-9"
            />
          </div>

          <div className="max-h-64 overflow-y-auto rounded-md border divide-y">
            {searchLoading ? (
              <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Searching...
              </div>
            ) : availableUsers.length === 0 ? (
              <div className="text-muted-foreground text-sm text-center py-4">
                No available users
              </div>
            ) : (
              availableUsers.map((u) => (
                <label
                  key={u.id}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-muted/50 cursor-pointer"
                >
                  <Checkbox
                    checked={selectedUserIds.has(u.id)}
                    onCheckedChange={() => toggleUser(u.id)}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{u.username}</div>
                    <div className="text-xs text-muted-foreground">
                      {u.first_name} {u.last_name} · {u.email}
                    </div>
                  </div>
                </label>
              ))
            )}
          </div>

          <div className="flex justify-end pt-1">
            <Button onClick={handleBulkAdd} disabled={adding || selectedUserIds.size === 0}>
              {adding && <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />}
              Add ({selectedUserIds.size})
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ---------- Audit Log Tab ----------

const ACTION_LABELS: Record<string, string> = {
  workspace_created: "Workspace Created",
  workspace_deleted: "Workspace Deleted",
  member_added: "Member Added",
  member_removed: "Member Removed",
  service_added: "Service Added",
  service_deleted: "Service Deleted",
  workflow_started: "Workflow Started",
  workflow_completed: "Workflow Completed",
  workflow_failed: "Workflow Failed",
  step_started: "Step Started",
  step_completed: "Step Completed",
  step_failed: "Step Failed",
}

function actionBadge(action: string) {
  const colors: Record<string, string> = {
    workspace_created: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    workspace_deleted: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    member_added: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    member_removed: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    service_added: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200",
    service_deleted: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
    workflow_started: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
    workflow_completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    workflow_failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    step_started: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    step_completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    step_failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  }
  return (
    <Badge className={`${colors[action] ?? ""} hover:${colors[action] ?? ""}`}>
      {ACTION_LABELS[action] ?? action}
    </Badge>
  )
}

function auditDetailSummary(action: string, detail: Record<string, unknown> | null): string | null {
  if (!detail) return null
  switch (action) {
    case "workflow_started":
      return `${detail.workflow_name} (${(detail.steps as string[])?.length ?? 0} steps)`
    case "workflow_completed":
      return `${detail.workflow_name} (${detail.steps_completed} steps, ${detail.duration_sec}s)`
    case "workflow_failed":
      return `${detail.workflow_name} — ${detail.failed_step ?? detail.failed_steps} failed`
    case "step_started":
    case "step_completed":
      return `${detail.step_name}`
    case "step_failed":
      return `${detail.step_name}: ${detail.error}`
    case "service_added":
    case "service_deleted":
      return `${detail.display_name ?? detail.plugin_name}${detail.endpoint ? ` → ${detail.endpoint}` : ""}`
    default:
      return null
  }
}

function AuditLogTab({ workspace }: { workspace: WorkspaceResponse }) {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const pageSize = 10

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchWorkspaceAuditLogs(workspace.id, page, pageSize)
      .then((data) => {
        if (!cancelled) { setLogs(data.items); setTotal(data.total) }
      })
      .catch(() => { if (!cancelled) setLogs([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [workspace.id, page])

  const totalPages = Math.ceil(total / pageSize)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (logs.length === 0) {
    return <div className="text-muted-foreground py-12 text-center text-sm">No audit logs</div>
  }

  return (
    <div className="space-y-3">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[160px]">Time</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead>Target User</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.map((log) => {
              const detail = auditDetailSummary(log.action, log.detail)
              return (
                <TableRow key={log.id}>
                  <TableCell className="text-sm font-mono">{formatDateTime(log.created_at)}</TableCell>
                  <TableCell>{actionBadge(log.action)}</TableCell>
                  <TableCell className="text-sm">{log.actor_username ?? "—"}</TableCell>
                  <TableCell className="text-sm">{log.target_username ?? "—"}</TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-[300px] truncate" title={detail ?? undefined}>
                    {detail ?? "—"}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}

// ---------- Main Export ----------

export function WorkspaceDetail({ workspace, onRefresh }: WorkspaceDetailProps) {
  return (
    <Tabs defaultValue="resources" className="w-full">
      <TabsList>
        <TabsTrigger value="resources">Resources</TabsTrigger>
        <TabsTrigger value="members">Members</TabsTrigger>
        <TabsTrigger value="audit">Audit Log</TabsTrigger>
      </TabsList>

      <TabsContent value="resources" className="mt-4">
        <ResourcesTab workspace={workspace} />
      </TabsContent>

      <TabsContent value="members" className="mt-4">
        <MembersTab workspace={workspace} onRefresh={onRefresh} />
      </TabsContent>

      <TabsContent value="audit" className="mt-4">
        <AuditLogTab workspace={workspace} />
      </TabsContent>
    </Tabs>
  )
}
