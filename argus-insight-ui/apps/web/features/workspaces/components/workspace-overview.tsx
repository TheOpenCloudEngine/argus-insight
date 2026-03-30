"use client"

import { useCallback, useEffect, useState } from "react"
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import { authFetch } from "@/features/auth/auth-fetch"
import { fetchWorkspace, fetchWorkspaceServices } from "@/features/workspaces/api"
import type { WorkspaceResponse, WorkspaceService } from "@/features/workspaces/types"
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

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(value)
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

function ServiceExpandedDetail({ service }: { service: WorkspaceService }) {
  const meta = service.metadata ?? {}

  // Collect all detail rows
  const details: { label: string; value: string; secret?: boolean; link?: boolean }[] = []

  if (service.endpoint) {
    details.push({ label: "Endpoint", value: service.endpoint, link: true })
  }
  if (service.username) {
    details.push({ label: "Username", value: service.username })
  }
  if (service.password) {
    details.push({ label: "Password", value: service.password, secret: true })
  }
  if (service.access_token) {
    details.push({ label: "Access Token", value: service.access_token, secret: true })
  }

  // Extract metadata fields
  for (const [key, val] of Object.entries(meta)) {
    if (val == null || val === "") continue
    const strVal = String(val)
    const label = key
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
    const isLink = /^https?:\/\//.test(strVal) || /^bolt:\/\//.test(strVal)
    details.push({ label, value: strVal, link: isLink })
  }

  details.push({ label: "Created", value: formatDateTime(service.created_at) })
  if (service.updated_at !== service.created_at) {
    details.push({ label: "Updated", value: formatDateTime(service.updated_at) })
  }

  return (
    <TableRow>
      <TableCell colSpan={5} className="bg-muted/30 p-0">
        <div className="grid gap-x-8 gap-y-2 px-6 py-4 sm:grid-cols-2">
          {details.map((d) => (
            <div key={d.label} className="flex items-center gap-2 text-sm">
              <span className="w-28 shrink-0 text-xs font-medium text-muted-foreground">
                {d.label}
              </span>
              {d.secret ? (
                <SecretValue value={d.value} label={d.label} />
              ) : d.link ? (
                <div className="flex items-center gap-1.5 min-w-0">
                  <a
                    href={d.value}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 truncate text-xs text-blue-600 hover:underline dark:text-blue-400"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {d.value}
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                  <CopyButton value={d.value} />
                </div>
              ) : (
                <div className="flex items-center gap-1.5 min-w-0">
                  <code className="truncate rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
                    {d.value}
                  </code>
                  <CopyButton value={d.value} />
                </div>
              )}
            </div>
          ))}
        </div>
        {/* Open Service button */}
        {service.endpoint && (
          <div className="border-t px-6 py-2">
            <a
              href={service.endpoint}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
            >
              <Button variant="outline" size="sm" className="text-xs">
                Open Service
                <ExternalLink className="ml-1.5 h-3 w-3" />
              </Button>
            </a>
          </div>
        )}
      </TableCell>
    </TableRow>
  )
}

function ServiceTable({ services }: { services: WorkspaceService[] }) {
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const toggle = (id: number) => {
    setExpandedId(expandedId === id ? null : id)
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10" />
            <TableHead>Service</TableHead>
            <TableHead className="hidden sm:table-cell">Version</TableHead>
            <TableHead className="hidden md:table-cell">Endpoint</TableHead>
            <TableHead className="w-24 text-center">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {services.map((svc) => {
            const iconName = svc.plugin_name.replace(/^argus-/, "").replace(/-deploy$/, "")
            const isExpanded = expandedId === svc.id

            return (
              <tbody key={svc.id}>
                <TableRow
                  className={`cursor-pointer ${isExpanded ? "bg-muted/50" : ""}`}
                  onClick={() => toggle(svc.id)}
                >
                  <TableCell className="w-10 px-3">
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <PluginIcon icon={iconName} size={24} className="shrink-0 rounded" />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {svc.display_name || svc.plugin_name}
                        </p>
                        <p className="truncate text-xs text-muted-foreground font-mono">
                          {svc.plugin_name}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                      {svc.version ? `v${svc.version}` : "-"}
                    </code>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {svc.endpoint ? (
                      <a
                        href={svc.endpoint}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 truncate text-xs text-blue-600 hover:underline dark:text-blue-400 max-w-[300px]"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {svc.endpoint}
                        <ExternalLink className="h-3 w-3 shrink-0" />
                      </a>
                    ) : (
                      <span className="text-xs text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    {statusBadge(svc.status)}
                  </TableCell>
                </TableRow>
                {isExpanded && <ServiceExpandedDetail service={svc} />}
              </tbody>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Workspace Resource Dashboard                                       */
/* ------------------------------------------------------------------ */

function WorkspaceResourceView({ workspaceId }: { workspaceId: number }) {
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null)
  const [services, setServices] = useState<WorkspaceService[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [ws, svc] = await Promise.all([
          fetchWorkspace(workspaceId),
          fetchWorkspaceServices(workspaceId),
        ])
        if (!cancelled) {
          setWorkspace(ws)
          setServices(svc)
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [workspaceId])

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

      {/* Summary Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Server className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-2xl font-bold">{services.length}</p>
              <p className="text-xs text-muted-foreground">Deployed Services</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <div>
              <p className="text-2xl font-bold">
                {services.filter((s) => s.status === "running").length}
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
                {services.filter((s) => s.status !== "running").length}
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

      {/* Service Table */}
      {services.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">
          No services deployed yet.
        </div>
      ) : (
        <div>
          <h3 className="mb-3 text-sm font-semibold">
            Deployed Services ({services.length})
          </h3>
          <ServiceTable services={services} />
        </div>
      )}
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
