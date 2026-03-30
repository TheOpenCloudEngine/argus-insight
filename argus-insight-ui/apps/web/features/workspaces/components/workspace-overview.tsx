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
  CardDescription,
  CardFooter,
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
import { deleteWorkspaceService, fetchWorkspace, fetchWorkspaceServices, fetchWorkspaceAuditLogs } from "@/features/workspaces/api"
import type { AuditLog, WorkspaceResponse, WorkspaceService } from "@/features/workspaces/types"
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
/*  My Workspace list (shown when no workspace is selected)            */
/* ------------------------------------------------------------------ */

function WorkspaceListView({ onSelect }: { onSelect: (ws: MyWorkspace) => void }) {
  const [workspaces, setWorkspaces] = useState<MyWorkspace[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    authFetch("/api/v1/workspace/workspaces/my")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        setWorkspaces(data)
        setLoading(false)
      })
      .catch(() => {
        setWorkspaces([])
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (workspaces.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 py-20">
        <Container className="h-12 w-12 text-muted-foreground" />
        <p className="text-muted-foreground">No workspaces found.</p>
        <p className="text-xs text-muted-foreground">
          Contact an administrator to create a workspace for you.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Select a workspace to view its resources.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {workspaces.map((ws) => (
          <Card
            key={ws.id}
            className="cursor-pointer transition-colors hover:bg-muted/50"
            onClick={() => onSelect(ws)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="truncate text-sm">{ws.display_name}</CardTitle>
                {statusBadge(ws.status)}
              </div>
              <CardDescription className="font-mono text-xs">
                {ws.name}
              </CardDescription>
            </CardHeader>
            <CardFooter className="pt-0">
              <Button variant="ghost" size="sm" className="ml-auto text-xs">
                Open
                <ExternalLink className="ml-1 h-3 w-3" />
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
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
  const iconName = service.plugin_name.replace(/^argus-/, "").replace(/-deploy$/, "")
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

  // Collect detail rows for expanded view
  const details: { label: string; value: string; secret?: boolean; link?: boolean }[] = []
  if (service.username) details.push({ label: "Username", value: service.username })
  if (service.password) details.push({ label: "Password", value: service.password, secret: true })
  if (service.access_token) details.push({ label: "Access Token", value: service.access_token, secret: true })
  // Display metadata entries
  for (const [key, val] of Object.entries(displayMeta)) {
    if (val == null || val === "") continue
    const strVal = String(val)
    const isLink = /^https?:\/\//.test(strVal) || /^bolt:\/\//.test(strVal)
    details.push({ label: key, value: strVal, link: isLink })
  }
  if (!hideTimestamps) {
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
          {displayUrl && (
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

        {/* Status badge */}
        <div className="shrink-0">
          {statusBadge(service.status)}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t bg-muted/20 px-4 py-4 pl-14">
          <div className="grid gap-x-10 gap-y-0.5 sm:grid-cols-2">
            {displayUrl && (
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
          {(openUrl || onDelete) && (
            <div className="mt-3 pt-3 border-t flex items-center justify-between">
              {openUrl ? (
                <a
                  href={openUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Button variant="outline" size="sm" className="text-xs">
                    Open Service
                    <ExternalLink className="ml-1.5 h-3 w-3" />
                  </Button>
                </a>
              ) : <div />}
              {onDelete && (
                <Button
                  variant="destructive"
                  size="sm"
                  className="text-xs"
                  onClick={(e) => { e.stopPropagation(); setConfirmOpen(true) }}
                >
                  Delete Service
                </Button>
              )}
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
}: {
  services: WorkspaceService[]
  hideTimestamps?: boolean
  onDelete?: (service: WorkspaceService) => void
}) {
  return (
    <div className="rounded-lg border">
      {services.map((svc) => (
        <ServiceDataListItem key={svc.id} service={svc} hideTimestamps={hideTimestamps} onDelete={onDelete} />
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Workspace Resource Dashboard                                       */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Add Service Button + Deploy Dialog                                 */
/* ------------------------------------------------------------------ */

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
  kserve: "argus-kserve",
  neo4j: "argus-neo4j",
  milvus: "argus-milvus",
  mindsdb: "argus-mindsdb",
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
        <DropdownMenuContent align="end">
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
                  <span className="flex-1">{item.service_label}</span>
                  {alreadyDeployed && (
                    <span className="ml-2 text-[10px] text-muted-foreground">(deployed)</span>
                  )}
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
      <Dialog open={deployOpen} onOpenChange={(open) => { if (!open) closeDeployDialog() }}>
        <DialogContent className="sm:max-w-sm">
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

          <div className="flex justify-end">
            {deployPhase === "progress" ? (
              <Button variant="outline" size="sm" disabled>
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                Deploying...
              </Button>
            ) : (
              <Button size="sm" onClick={closeDeployDialog}>Close</Button>
            )}
          </div>
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
        const [ws, svc, gitlabRes, cfgRes] = await Promise.all([
          fetchWorkspace(workspaceId),
          fetchWorkspaceServices(workspaceId),
          authFetch("/api/v1/settings/gitlab").catch(() => null),
          authFetch("/api/v1/settings/configuration").catch(() => null),
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
            {workspace.k8s_namespace && (
              <>
                <span className="mx-2 text-muted-foreground/50">|</span>
                <span className="font-mono">{workspace.k8s_namespace}</span>
              </>
            )}
            {workspace.domain && (
              <>
                <span className="mx-2 text-muted-foreground/50">|</span>
                {workspace.domain}
              </>
            )}
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

            // Inject GitLab password from user profile
            return {
              ...svc,
              endpoint,
              password: user?.gitlab_password || null,
            }
          })

        // Deployed services (everything except hidden + default)
        const deployed = all.filter((s) => !defaultPlugins.has(s.plugin_name))

        return (
          <>
            {/* Summary Stats */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardContent className="flex items-center gap-3 p-4">
                  <Server className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{deployed.length}</p>
                    <p className="text-xs text-muted-foreground">Deployed Services</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="flex items-center gap-3 p-4">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  <div>
                    <p className="text-2xl font-bold">
                      {deployed.filter((s) => s.status === "running").length}
                    </p>
                    <p className="text-xs text-muted-foreground">Running</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="flex items-center gap-3 p-4">
                  <XCircle className="h-5 w-5 text-red-500" />
                  <div>
                    <p className="text-2xl font-bold">
                      {deployed.filter((s) => s.status !== "running").length}
                    </p>
                    <p className="text-xs text-muted-foreground">Not Running</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="flex items-center gap-3 p-4">
                  <Clock className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">
                      {new Date(workspace.created_at).toLocaleDateString()}
                    </p>
                    <p className="text-xs text-muted-foreground">Created</p>
                  </div>
                </CardContent>
              </Card>
            </div>

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
                <ServiceDataList services={deployed} onDelete={handleDeleteService} />
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

export function WorkspaceOverview() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const wsId = searchParams.get("ws")

  const handleSelectWorkspace = useCallback(
    (ws: MyWorkspace) => {
      router.push(`/dashboard/workspace?ws=${ws.id}`)
    },
    [router],
  )

  if (wsId) {
    return <WorkspaceResourceView workspaceId={Number(wsId)} />
  }

  return <WorkspaceListView onSelect={handleSelectWorkspace} />
}
