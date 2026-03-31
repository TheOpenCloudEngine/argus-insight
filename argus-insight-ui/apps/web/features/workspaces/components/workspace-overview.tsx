"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Container,
  ExternalLink,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  Server,
  XCircle,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
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
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import { authFetch } from "@/features/auth/auth-fetch"
import { useAuth } from "@/features/auth"
import { Avatar, AvatarFallback } from "@workspace/ui/components/avatar"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { Input } from "@workspace/ui/components/input"
import {
  bulkAddWorkspaceMembers,
  deleteWorkspaceService,
  fetchWorkspace,
  fetchWorkspaceMembers,
  fetchWorkspaceServices,
  fetchWorkspaceAuditLogs,
  removeWorkspaceMember,
} from "@/features/workspaces/api"
import type { AuditLog, WorkspaceMember, WorkspaceResponse, WorkspaceService } from "@/features/workspaces/types"
import { PluginIcon } from "@/features/software-deployment/components/plugin-icon"

/* ------------------------------------------------------------------ */
/*  Shared helpers                                                     */
/* ------------------------------------------------------------------ */

interface MyWorkspace {
  id: number
  name: string
  display_name: string
  status: string
}

function statusBadge(status: string) {
  switch (status) {
    case "active":
    case "running":
      return (
        <Badge className="bg-green-100 text-green-800 hover:bg-green-100 dark:bg-green-900 dark:text-green-200">
          <CheckCircle2 className="mr-1 h-3 w-3" />
          {status === "active" ? "Active" : "Running"}
        </Badge>
      )
    case "provisioning":
      return (
        <Badge className="animate-pulse bg-blue-100 text-blue-800 hover:bg-blue-100 dark:bg-blue-900 dark:text-blue-200">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          Provisioning
        </Badge>
      )
    case "failed":
      return (
        <Badge className="bg-red-100 text-red-800 hover:bg-red-100 dark:bg-red-900 dark:text-red-200">
          <XCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      )
    default:
      return (
        <Badge variant="secondary">
          <Clock className="mr-1 h-3 w-3" />
          {status}
        </Badge>
      )
  }
}

function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      // Fallback for non-HTTPS environments (e.g., http://10.0.1.50)
      const textarea = document.createElement("textarea")
      textarea.value = value
      textarea.style.position = "fixed"
      textarea.style.opacity = "0"
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand("copy")
      document.body.removeChild(textarea)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={handleCopy}
          className="text-muted-foreground hover:text-foreground"
        >
          {copied ? (
            <CheckCircle2 className="h-3 w-3 text-green-600" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="text-xs">
        {copied ? "Copied!" : "Copy"}
      </TooltipContent>
    </Tooltip>
  )
}

function SecretValue({ value, label }: { value: string; label: string }) {
  const [show, setShow] = useState(false)

  return (
    <div className="flex items-center gap-1.5">
      <code className="max-w-[220px] truncate rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
        {show ? value : "••••••••••••"}
      </code>
      <button
        onClick={(e) => { e.stopPropagation(); setShow(!show) }}
        className="text-muted-foreground hover:text-foreground"
      >
        {show ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
      </button>
      {show && <CopyButton value={value} />}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Empty state (no workspaces)                                        */
/* ------------------------------------------------------------------ */

function NoWorkspaceView() {
  const router = useRouter()
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 py-20">
      <Container className="h-14 w-14 text-muted-foreground" />
      <h2 className="text-lg font-semibold">No Workspace Available</h2>
      <p className="text-sm text-muted-foreground text-center max-w-md">
        Create a workspace to start collaborating with your team.
        You can deploy services, analyze data, and manage resources
        in a shared environment.
      </p>
      <Button onClick={() => router.push("/dashboard/workspaces")}>
        Create Workspace
      </Button>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Expandable Service Row                                             */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  OpenShift-style Data List                                          */
/* ------------------------------------------------------------------ */

function DetailRow({
  label,
  value,
  secret,
  link,
}: {
  label: string
  value: string
  secret?: boolean
  link?: boolean
}) {
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="w-28 shrink-0 text-xs font-medium text-muted-foreground">
        {label}
      </span>
      {secret ? (
        <SecretValue value={value} label={label} />
      ) : link ? (
        <div className="flex items-center gap-1.5 min-w-0">
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 truncate text-xs text-blue-600 hover:underline dark:text-blue-400"
            onClick={(e) => e.stopPropagation()}
          >
            {value}
            <ExternalLink className="h-3 w-3 shrink-0" />
          </a>
          <CopyButton value={value} />
        </div>
      ) : (
        <div className="flex items-center gap-1.5 min-w-0">
          <code className="truncate rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
            {value}
          </code>
          <CopyButton value={value} />
        </div>
      )}
    </div>
  )
}

function ServiceDataListItem({
  service,
  hideTimestamps,
  onDelete,
}: {
  service: WorkspaceService
  hideTimestamps?: boolean
  onDelete?: (service: WorkspaceService) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  // Map plugin_name to icon filename
  const PLUGIN_ICON_MAP: Record<string, string> = {
    "argus-vscode-server": "code",
    "argus-minio": "minio",
    "argus-minio-deploy": "minio",
  }
  const iconName = PLUGIN_ICON_MAP[service.plugin_name]
    ?? service.plugin_name.replace(/^argus-/, "").replace(/-deploy$/, "")
  const meta = service.metadata ?? {}

  // Extract display metadata (new format: metadata.display)
  // Falls back to flat metadata for backward compatibility
  const displayMeta: Record<string, unknown> =
    meta.display && typeof meta.display === "object" && !Array.isArray(meta.display)
      ? (meta.display as Record<string, unknown>)
      : (() => {
          // Legacy flat format: exclude known internal keys
          const internalKeys = new Set([
            "internal", "display", "namespace",
            "internal_endpoint", "internal_bolt", "internal_http",
            "internal_grpc", "internal_attu", "internal_mysql", "internal_mongodb",
            "bolt_port", "http_port", "grpc_port", "attu_port",
            "mysql_port", "mongodb_port", "project_id",
          ])
          const result: Record<string, unknown> = {}
          for (const [k, v] of Object.entries(meta)) {
            if (!internalKeys.has(k) && v != null && v !== "") result[k] = v
          }
          return result
        })()

  // Determine display URL: prefer display metadata URLs, then endpoint
  const firstHttpUrl = Object.values(displayMeta).find(
    (v) => typeof v === "string" && /^https?:\/\//.test(v),
  ) as string | undefined
  const displayUrl = firstHttpUrl || service.endpoint
  const openUrl =
    firstHttpUrl ||
    (service.endpoint && /^https?:\/\//.test(service.endpoint) ? service.endpoint : null)

  // Custom labels (injected by GitLab default service mapping)
  const svcAny = service as WorkspaceService & { _usernameLabel?: string; _passwordLabel?: string; _hideUrl?: boolean; _hideTimestamps?: boolean }
  const usernameLabel = svcAny._usernameLabel || "Username"
  const passwordLabel = svcAny._passwordLabel || "Password"
  const hideUrl = svcAny._hideUrl || false
  const effectiveHideTimestamps = hideTimestamps || svcAny._hideTimestamps || false

  // Collect detail rows for expanded view
  const details: { label: string; value: string; secret?: boolean; link?: boolean }[] = []
  if (service.username) details.push({ label: usernameLabel, value: service.username })
  if (service.password) details.push({ label: passwordLabel, value: service.password, secret: true })
  if (service.access_token) details.push({ label: "Access Token", value: service.access_token, secret: true })
  // Display metadata entries
  for (const [key, val] of Object.entries(displayMeta)) {
    if (val == null || val === "") continue
    const strVal = String(val)
    const isLink = /^https?:\/\//.test(strVal) || /^bolt:\/\//.test(strVal)
    const isSecret = /password/i.test(key)
    details.push({ label: key, value: strVal, link: isLink, secret: isSecret })
  }
  if (!effectiveHideTimestamps) {
    details.push({ label: "Created", value: formatDateTime(service.created_at) })
    if (service.updated_at !== service.created_at) {
      details.push({ label: "Updated", value: formatDateTime(service.updated_at) })
    }
  }

  return (
    <div className="border-b last:border-b-0">
      {/* Collapsed row */}
      <div
        className={`flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/40 ${expanded ? "bg-muted/30" : ""}`}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Chevron */}
        <div className="shrink-0">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>

        {/* Icon + Name */}
        <PluginIcon icon={iconName} size={28} className="shrink-0 rounded" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold">
              {service.display_name || service.plugin_name}
            </span>
            <code className="hidden shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground sm:inline">
              {service.version ? `v${service.version}` : service.plugin_name}
            </code>
          </div>
          {/* Primary URL inline */}
          {displayUrl && !hideUrl && (
            <a
              href={openUrl || displayUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 truncate text-xs text-blue-600 hover:underline dark:text-blue-400"
              onClick={(e) => e.stopPropagation()}
            >
              {displayUrl}
              <ExternalLink className="h-3 w-3 shrink-0" />
            </a>
          )}
        </div>

        {/* Status badge + Open Service */}
        <div className="flex items-center gap-2 shrink-0">
          {statusBadge(service.status)}
          {openUrl && (
            <a
              href={openUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
            >
              <Button variant="outline" size="sm" className="text-xs h-6 px-2">
                Open
                <ExternalLink className="ml-1 h-3 w-3" />
              </Button>
            </a>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t bg-muted/20 px-4 py-4 pl-14">
          <div className="grid gap-x-10 gap-y-0.5 sm:grid-cols-2">
            {displayUrl && !hideUrl && (
              <DetailRow label="URL" value={displayUrl} link />
            )}
            {details.map((d) => (
              <DetailRow
                key={d.label}
                label={d.label}
                value={d.value}
                secret={d.secret}
                link={d.link}
              />
            ))}
          </div>
          {onDelete && (
            <div className="mt-3 flex items-center justify-end">
              <Button
                variant="destructive"
                size="sm"
                className="text-xs"
                onClick={(e) => { e.stopPropagation(); setConfirmOpen(true) }}
              >
                Delete Service
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={confirmOpen} onOpenChange={(open) => { if (!open && !deleting) setConfirmOpen(false) }}>
        <DialogContent className="sm:max-w-sm" onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Delete Service</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this service? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmOpen(false)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={deleting}
              onClick={async () => {
                setDeleting(true)
                try {
                  await onDelete?.(service)
                } finally {
                  setDeleting(false)
                  setConfirmOpen(false)
                }
              }}
            >
              {deleting ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ServiceDataList({
  services,
  hideTimestamps,
  onDelete,
  isOwner,
  perUserPlugins,
}: {
  services: WorkspaceService[]
  hideTimestamps?: boolean
  onDelete?: (service: WorkspaceService) => void
  isOwner?: boolean
  perUserPlugins?: Set<string>
}) {
  return (
    <div className="rounded-lg border">
      {services.map((svc) => {
        // per_user services: user can delete their own
        // per_workspace services: only owner can delete
        const canDelete = onDelete
          ? isOwner || (perUserPlugins?.has(svc.plugin_name) ?? false)
          : false
        return (
          <ServiceDataListItem
            key={svc.id}
            service={svc}
            hideTimestamps={hideTimestamps}
            onDelete={canDelete ? onDelete : undefined}
          />
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Workspace Resource Dashboard                                       */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Add Service Button + Deploy Dialog                                 */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Workspace Members                                                  */
/* ------------------------------------------------------------------ */

function memberInitials(m: WorkspaceMember): string {
  if (m.display_name) {
    const parts = m.display_name.split(" ")
    return parts.length >= 2
      ? (parts[0]![0]! + parts[1]![0]!).toUpperCase()
      : m.display_name.slice(0, 2).toUpperCase()
  }
  return (m.username ?? "?").slice(0, 2).toUpperCase()
}

function WorkspaceMembersBar({
  workspaceId,
  isOwner,
  refreshKey,
  onRefresh,
}: {
  workspaceId: number
  isOwner: boolean
  refreshKey: number
  onRefresh: () => void
}) {
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [loading, setLoading] = useState(true)

  // Add dialog
  const [addOpen, setAddOpen] = useState(false)
  const [searchResults, setSearchResults] = useState<{ id: number; username: string; display_name?: string }[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set())
  const [adding, setAdding] = useState(false)

  // Remove confirm
  const [removeTarget, setRemoveTarget] = useState<WorkspaceMember | null>(null)
  const [removing, setRemoving] = useState(false)

  useEffect(() => {
    fetchWorkspaceMembers(workspaceId)
      .then(setMembers)
      .catch(() => setMembers([]))
      .finally(() => setLoading(false))
  }, [workspaceId, refreshKey])

  const openAddDialog = () => {
    setAddOpen(true)
    setSearchQuery("")
    setSearchResults([])
    setSearched(false)
    setSelectedUserIds(new Set())
    setAdding(false)
  }

  const handleSearch = async () => {
    const q = searchQuery.trim()
    if (!q) return
    setSearching(true)
    setSearched(true)
    try {
      const res = await authFetch(`/api/v1/usermgr/users?page_size=50&search=${encodeURIComponent(q)}`)
      if (res.ok) {
        const data = await res.json()
        setSearchResults(
          (data.items ?? []).map((u: { id: number; username: string; first_name?: string; last_name?: string }) => ({
            id: u.id,
            username: u.username,
            display_name: [u.first_name, u.last_name].filter(Boolean).join(" ") || u.username,
          })),
        )
      }
    } catch { /* ignore */ }
    setSearching(false)
  }

  const toggleUser = (userId: number) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev)
      if (next.has(userId)) next.delete(userId)
      else next.add(userId)
      return next
    })
  }

  const handleAdd = async () => {
    if (selectedUserIds.size === 0) return
    setAdding(true)
    try {
      await bulkAddWorkspaceMembers(workspaceId, Array.from(selectedUserIds))
      setAddOpen(false)
      const updated = await fetchWorkspaceMembers(workspaceId)
      setMembers(updated)
      onRefresh()
    } catch { /* ignore */ }
    setAdding(false)
  }

  const handleRemove = async () => {
    if (!removeTarget) return
    setRemoving(true)
    try {
      await removeWorkspaceMember(workspaceId, removeTarget.id)
      setMembers((prev) => prev.filter((m) => m.id !== removeTarget.id))
      onRefresh()
    } catch { /* ignore */ }
    setRemoving(false)
    setRemoveTarget(null)
  }

  const memberIds = new Set(members.map((m) => m.user_id))
  const filteredUsers = searchResults.filter((u) => !memberIds.has(u.id))

  return (
    <>
      <div className="rounded-lg border p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Members ({members.length})</h3>
          {isOwner && (
            <Button variant="outline" size="sm" className="text-xs" onClick={openAddDialog}>
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              Add Member
            </Button>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : members.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">No members.</p>
        ) : (
          <div className="flex flex-wrap gap-3">
            {members.map((m) => (
              <div key={m.id} className="group relative flex flex-col items-center gap-1 w-20">
                {/* X button (hover only, visible to workspace owner, not on owner member) */}
                {isOwner && !m.is_owner && (
                  <button
                    className="absolute -top-1 -right-1 hidden group-hover:flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white text-[10px] leading-none hover:bg-red-600 z-10"
                    onClick={() => setRemoveTarget(m)}
                  >
                    ✕
                  </button>
                )}
                <Avatar className="h-9 w-9">
                  <AvatarFallback className="text-sm">{memberInitials(m)}</AvatarFallback>
                </Avatar>
                <span className="truncate text-sm text-center w-full">
                  {m.display_name || m.username}
                </span>
                {m.is_owner && (
                  <Badge variant="secondary" className="text-xs px-1.5 py-0">Owner</Badge>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Member Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Add Member</DialogTitle>
            <DialogDescription>Search for users by username or name and press Enter.</DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Enter username and press Enter..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSearch() }}
          />
          <div className="max-h-48 overflow-y-auto space-y-1 rounded-md border p-2">
            {searching ? (
              <div className="flex items-center justify-center gap-2 py-4">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Searching...</span>
              </div>
            ) : !searched ? (
              <p className="text-xs text-muted-foreground text-center py-4">Type a username and press Enter to search.</p>
            ) : filteredUsers.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-2">No users found.</p>
            ) : (
              filteredUsers.map((u) => (
                <label
                  key={u.id}
                  className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-muted/50 cursor-pointer"
                >
                  <Checkbox
                    checked={selectedUserIds.has(u.id)}
                    onCheckedChange={() => toggleUser(u.id)}
                  />
                  <span className="text-sm">{u.display_name || u.username}</span>
                  <span className="text-xs text-muted-foreground ml-auto">{u.username}</span>
                </label>
              ))
            )}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleAdd} disabled={adding || selectedUserIds.size === 0}>
              {adding && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Add ({selectedUserIds.size})
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Remove Confirm Dialog */}
      <Dialog open={!!removeTarget} onOpenChange={(open) => { if (!open) setRemoveTarget(null) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Remove Member</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove {removeTarget?.display_name || removeTarget?.username} from this workspace?
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setRemoveTarget(null)} disabled={removing}>Cancel</Button>
            <Button variant="destructive" size="sm" onClick={handleRemove} disabled={removing}>
              {removing && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Remove
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

interface DeployMappingEntry {
  service_key: string
  service_label: string
  icon: string
  pipeline_id: number | null
  pipeline_name: string | null
  constraint: string      // "per_workspace" | "per_user"
  constraint_label: string
}

// Map service_key to plugin_name patterns used in workspace services
const SERVICE_KEY_TO_PLUGIN: Record<string, string> = {
  mlflow: "argus-mlflow",
  vscode: "argus-vscode-server",
  airflow: "argus-airflow",
  jupyter: "argus-jupyter",
  jupyter_tensorflow: "argus-jupyter-tensorflow",
  kserve: "argus-kserve",
  neo4j: "argus-neo4j",
  milvus: "argus-milvus",
  mindsdb: "argus-mindsdb",
  trino: "argus-trino",
  starrocks: "argus-starrocks",
  postgresql: "argus-postgresql",
  mariadb: "argus-mariadb",
}

function AddServiceButton({
  workspace,
  services,
  onDeployComplete,
}: {
  workspace: WorkspaceResponse
  services: WorkspaceService[]
  onDeployComplete: () => void
}) {
  const { user } = useAuth()
  const [menuItems, setMenuItems] = useState<DeployMappingEntry[]>([])

  // Confirm dialog state
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingItem, setPendingItem] = useState<DeployMappingEntry | null>(null)

  // Deploy progress dialog state
  const [deployOpen, setDeployOpen] = useState(false)
  const [deployLabel, setDeployLabel] = useState("")
  const [deployPhase, setDeployPhase] = useState<"progress" | "done" | "error">("progress")
  const [deployError, setDeployError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load deploy mappings
  useEffect(() => {
    authFetch("/api/v1/settings/deploy-mapping")
      .then((res) => (res.ok ? res.json() : { mappings: [] }))
      .then((data) => {
        // Only show services that have a pipeline mapped
        setMenuItems((data.mappings ?? []).filter((m: DeployMappingEntry) => m.pipeline_id))
      })
      .catch(() => setMenuItems([]))
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [])

  const handleMenuClick = (item: DeployMappingEntry) => {
    setPendingItem(item)
    setConfirmOpen(true)
  }

  const handleConfirmDeploy = async () => {
    if (!pendingItem) return
    const item = pendingItem
    setConfirmOpen(false)
    setPendingItem(null)

    setDeployLabel(item.service_label)
    setDeployPhase("progress")
    setDeployError(null)
    setDeployOpen(true)

    const pipelineId = item.pipeline_id
    if (!pipelineId) {
      setDeployError(`No pipeline mapped for "${item.service_label}". Configure it in Software Deployment > Pipeline To Deployment.`)
      setDeployPhase("error")
      return
    }

    // Deploy
    try {
      const res = await authFetch(`/api/v1/workspace/workspaces/${workspace.id}/deploy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pipeline_id: pipelineId }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Deploy failed: ${res.status}`)
      }
    } catch (e) {
      setDeployError(e instanceof Error ? e.message : "Deploy failed")
      setDeployPhase("error")
      return
    }

    // Poll audit logs for completion
    const pollStartedAt = new Date().toISOString()
    pollingRef.current = setInterval(async () => {
      try {
        const data = await fetchWorkspaceAuditLogs(workspace.id, 1, 50)
        const recent = data.items.filter((l) => l.created_at >= pollStartedAt)

        const completed = recent.find((l) =>
          l.action === "workflow_completed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        const failed = recent.find((l) =>
          l.action === "workflow_failed" &&
          (l.detail as Record<string, unknown>)?.workflow_name === "workspace-provision"
        )
        if (completed) {
          if (pollingRef.current) clearInterval(pollingRef.current)
          pollingRef.current = null
          setDeployPhase("done")
          onDeployComplete()
        } else if (failed) {
          if (pollingRef.current) clearInterval(pollingRef.current)
          pollingRef.current = null
          setDeployError(String((failed.detail as Record<string, unknown>)?.error || "Deployment failed"))
          setDeployPhase("error")
          onDeployComplete()
        }
      } catch { /* ignore */ }
    }, 2000)
  }

  const closeDeployDialog = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    setDeployOpen(false)
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="text-xs">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add Service
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {menuItems.length === 0 ? (
            <DropdownMenuItem disabled>
              <span className="text-muted-foreground text-xs">No services configured</span>
            </DropdownMenuItem>
          ) : (
            menuItems.map((item) => {
              const pluginName = SERVICE_KEY_TO_PLUGIN[item.service_key]
              const isProvisioning = workspace.status === "provisioning"

              // Check constraint
              let alreadyDeployed = false
              if (item.constraint === "per_workspace" && pluginName) {
                alreadyDeployed = services.some((s) => s.plugin_name === pluginName)
              } else if (item.constraint === "per_user" && pluginName && user) {
                // per_user: check if current user already has this service
                // (service metadata or username match)
                alreadyDeployed = services.some(
                  (s) => s.plugin_name === pluginName && s.username === user.username,
                )
              }

              return (
                <DropdownMenuItem
                  key={item.service_key}
                  onClick={() => !alreadyDeployed && handleMenuClick(item)}
                  disabled={isProvisioning || alreadyDeployed}
                >
                  <PluginIcon icon={item.icon} size={16} className="mr-2 rounded" />
                  {item.service_label}
                </DropdownMenuItem>
              )
            })
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Confirm Deploy Dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Deploy Service</DialogTitle>
            <DialogDescription>
              Would you like to deploy {pendingItem?.service_label} to this workspace?
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleConfirmDeploy}>
              OK
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Deploy Progress Dialog */}
      <Dialog open={deployOpen} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-sm [&>button]:hidden" onPointerDownOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle>
              {deployPhase === "progress" && `Deploying ${deployLabel}`}
              {deployPhase === "done" && `${deployLabel} Deployed`}
              {deployPhase === "error" && `${deployLabel} Deployment`}
            </DialogTitle>
          </DialogHeader>

          <div className="py-4">
            {deployPhase === "progress" && (
              <div className="flex flex-col items-center gap-3 py-4">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Please wait a moment...</p>
              </div>
            )}
            {deployPhase === "done" && (
              <div className="rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-2 text-sm dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800">
                Service has been deployed successfully.
              </div>
            )}
            {deployPhase === "error" && deployError && (
              <div className="rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm dark:bg-red-950 dark:text-red-200 dark:border-red-800">
                {deployError}
              </div>
            )}
          </div>

          {deployPhase !== "progress" && (
            <div className="flex justify-center">
              <Button size="sm" onClick={closeDeployDialog}>Close</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  Workspace Resource Dashboard                                       */
/* ------------------------------------------------------------------ */

function WorkspaceResourceView({ workspaceId }: { workspaceId: number }) {
  const { user } = useAuth()
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null)
  const [services, setServices] = useState<WorkspaceService[]>([])
  const [gitlabServerUrl, setGitlabServerUrl] = useState<string>("")
  const [perUserPlugins, setPerUserPlugins] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  const handleDeployComplete = useCallback(() => {
    setRefreshKey((k) => k + 1)
  }, [])

  const handleDeleteService = useCallback(async (svc: WorkspaceService) => {
    await deleteWorkspaceService(workspaceId, svc.id)
    setRefreshKey((k) => k + 1)
  }, [workspaceId])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [ws, svc, gitlabRes, cfgRes, mappingRes] = await Promise.all([
          fetchWorkspace(workspaceId),
          fetchWorkspaceServices(workspaceId),
          authFetch("/api/v1/settings/gitlab").catch(() => null),
          authFetch("/api/v1/settings/configuration").catch(() => null),
          authFetch("/api/v1/settings/deploy-mapping").catch(() => null),
        ])
        if (!cancelled) {
          setWorkspace(ws)
          setServices(svc)
          // Try /settings/gitlab first, fall back to /settings/configuration
          let glUrl = ""
          if (gitlabRes?.ok) {
            const data = await gitlabRes.json()
            glUrl = data.url || ""
          }
          if (!glUrl && cfgRes?.ok) {
            const data = await cfgRes.json()
            const gitlabCat = data.categories?.find(
              (c: { category: string }) => c.category === "gitlab",
            )
            glUrl = gitlabCat?.items?.gitlab_url || ""
          }
          if (glUrl) setGitlabServerUrl(glUrl.replace(/\/+$/, ""))

          // Build set of per_user plugin names
          if (mappingRes?.ok) {
            const mData = await mappingRes.json()
            const perUser = new Set<string>()
            for (const m of mData.mappings ?? []) {
              if (m.constraint === "per_user") {
                const pluginName = SERVICE_KEY_TO_PLUGIN[m.service_key as string]
                if (pluginName) perUser.add(pluginName)
              }
            }
            setPerUserPlugins(perUser)
          }
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [workspaceId, refreshKey])

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!workspace) {
    return (
      <div className="flex flex-1 items-center justify-center py-20 text-muted-foreground">
        Workspace not found.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="flex items-center gap-4">
        <div>
          <h2 className="text-lg font-semibold">{workspace.display_name}</h2>
          <p className="text-sm text-muted-foreground">
            <span className="font-mono">{workspace.name}</span>
            <span className="mx-2 text-muted-foreground/50">|</span>
            <span>{formatDateTime(workspace.created_at)}</span>
          </p>
        </div>
        <div className="ml-auto">{statusBadge(workspace.status)}</div>
      </div>

      {(() => {
        // Categorize services
        const hiddenPlugins = new Set(["argus-minio-workspace", "argus-minio-setup"])
        const defaultPlugins = new Set(["argus-gitlab"])
        const all = services.filter((s) => !hiddenPlugins.has(s.plugin_name))

        // Default services (GitLab etc.) — always present for every workspace
        const defaultServices = all
          .filter((s) => defaultPlugins.has(s.plugin_name))
          .map((svc) => {
            if (svc.plugin_name !== "argus-gitlab") return svc

            // Reconstruct GitLab URL from Settings server URL + project path
            const rawUrl = workspace.gitlab_project_url || svc.endpoint
            let endpoint = rawUrl || ""
            if (gitlabServerUrl && rawUrl) {
              try {
                const parsed = new URL(rawUrl)
                endpoint = `${gitlabServerUrl}${parsed.pathname}`
              } catch { /* use rawUrl */ }
            }

            // Use user's GitLab credentials instead of service-level ones
            return {
              ...svc,
              endpoint,
              username: user?.gitlab_username || svc.username,
              password: user?.gitlab_password || null,
              // Custom display labels for expanded detail
              _usernameLabel: "Gitlab Username",
              _passwordLabel: "Gitlab Password",
              _hideUrl: true,
            } as WorkspaceService & { _usernameLabel?: string; _passwordLabel?: string; _hideUrl?: boolean }
          })

        // Deployed services (everything except hidden + default)
        // For per_user services, only show current user's instances
        const deployed = all
          .filter((s) => {
            if (defaultPlugins.has(s.plugin_name)) return false
            if (perUserPlugins.has(s.plugin_name) && user) {
              return s.username === user.username
            }
            return true
          })
          .map((svc) => {
            if (svc.plugin_name === "argus-mariadb" || svc.plugin_name === "argus-postgresql") {
              return {
                ...svc,
                username: null,
                password: null,
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name === "argus-mlflow" || svc.plugin_name === "argus-airflow") {
              return {
                ...svc,
                username: svc.plugin_name === "argus-mlflow" ? null : svc.username,
                metadata: { ...svc.metadata, display: {} },
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name === "argus-vscode-server") {
              return {
                ...svc,
                username: null,
                metadata: {
                  ...svc.metadata,
                  display: {
                    "Workspace Bucket": "/workspace",
                    "User Bucket": "/data",
                  },
                },
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            if (svc.plugin_name.startsWith("argus-jupyter")) {
              return {
                ...svc,
                username: null,
                metadata: {
                  ...svc.metadata,
                  display: {
                    "Workspace": "/workspace (Workspace Bucket)",
                    "User": "/data (User Bucket)",
                  },
                },
                _hideUrl: true,
                _hideTimestamps: true,
              } as WorkspaceService & { _hideUrl?: boolean; _hideTimestamps?: boolean }
            }
            return svc
          })

        return (
          <>
            {/* Members */}
            <WorkspaceMembersBar
              workspaceId={workspace.id}
              isOwner={!!user && String(workspace.created_by) === user.sub}
              refreshKey={refreshKey}
              onRefresh={handleDeployComplete}
            />

            {/* Default Services */}
            {defaultServices.length > 0 && (
              <div>
                <h3 className="mb-3 text-sm font-semibold">
                  Default Services ({defaultServices.length})
                </h3>
                <ServiceDataList services={defaultServices} hideTimestamps />
              </div>
            )}

            {/* Deployed Services */}
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold">
                  Deployed Services ({deployed.length})
                </h3>
                <AddServiceButton
                  workspace={workspace}
                  services={services}
                  onDeployComplete={handleDeployComplete}
                />
              </div>
              {deployed.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground text-sm rounded-lg border">
                  No services deployed yet. Click "Add Service" to deploy one.
                </div>
              ) : (
                <ServiceDataList
                  services={deployed}
                  onDelete={handleDeleteService}
                  isOwner={!!user && String(workspace.created_by) === user.sub}
                  perUserPlugins={perUserPlugins}
                />
              )}
            </div>
          </>
        )
      })()}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main component: switches between list and resource view            */
/* ------------------------------------------------------------------ */

const WS_SESSION_KEY = "argus_last_workspace_id"

export function WorkspaceOverview() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const wsId = searchParams.get("ws")
  const [checked, setChecked] = useState(false)

  // If ws param present, remember it
  useEffect(() => {
    if (wsId) {
      sessionStorage.setItem(WS_SESSION_KEY, wsId)
      setChecked(true)
    }
  }, [wsId])

  // If no ws param, try last selected or first available
  useEffect(() => {
    if (wsId) return

    // Try last selected workspace from session
    const lastId = sessionStorage.getItem(WS_SESSION_KEY)
    if (lastId) {
      router.replace(`/dashboard/workspace?ws=${lastId}`)
      return
    }

    // No last selection — fetch and pick first
    authFetch("/api/v1/workspace/workspaces/my")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: MyWorkspace[]) => {
        if (data.length > 0) {
          router.replace(`/dashboard/workspace?ws=${data[0].id}`)
        } else {
          setChecked(true)
        }
      })
      .catch(() => setChecked(true))
  }, [wsId, router])

  if (!checked) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (wsId) {
    return <WorkspaceResourceView workspaceId={Number(wsId)} />
  }

  return <NoWorkspaceView />
}
