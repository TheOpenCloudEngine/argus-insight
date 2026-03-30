"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  CheckCircle2,
  Clock,
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
import { authFetch } from "@/features/auth/auth-fetch"
import { fetchWorkspace, fetchWorkspaceServices } from "@/features/workspaces/api"
import type { WorkspaceResponse, WorkspaceService } from "@/features/workspaces/types"
import { PluginIcon } from "@/features/software-deployment/components/plugin-icon"

/* ------------------------------------------------------------------ */
/*  My Workspace list (shown when no workspace is selected)            */
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
      return (
        <Badge className="bg-green-100 text-green-800 hover:bg-green-100 dark:bg-green-900 dark:text-green-200">
          <CheckCircle2 className="mr-1 h-3 w-3" />
          Active
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
/*  Workspace Resource Dashboard (shown when workspace is selected)    */
/* ------------------------------------------------------------------ */

function ServiceCard({ service }: { service: WorkspaceService }) {
  const [showPw, setShowPw] = useState(false)
  const [showToken, setShowToken] = useState(false)

  // Derive icon name from plugin_name (e.g., "argus-airflow" → "airflow")
  const iconName = service.plugin_name.replace(/^argus-/, "").replace(/-deploy$/, "")

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-3 pb-2">
        <PluginIcon icon={iconName} size={28} className="shrink-0 rounded" />
        <div className="min-w-0 flex-1">
          <CardTitle className="truncate text-sm">
            {service.display_name || service.plugin_name}
          </CardTitle>
          <CardDescription className="text-xs">
            {service.version ? `v${service.version}` : service.plugin_name}
          </CardDescription>
        </div>
        <Badge
          variant="secondary"
          className={
            service.status === "running"
              ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
              : ""
          }
        >
          {service.status}
        </Badge>
      </CardHeader>

      <CardContent className="space-y-2 pt-0 text-sm">
        {/* Endpoint */}
        {service.endpoint && (
          <div className="flex items-start gap-2">
            <span className="text-muted-foreground w-16 shrink-0 text-xs">Endpoint</span>
            <a
              href={service.endpoint}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 truncate text-xs text-blue-600 hover:underline dark:text-blue-400"
            >
              {service.endpoint}
              <ExternalLink className="h-3 w-3 shrink-0" />
            </a>
          </div>
        )}

        {/* Username */}
        {service.username && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-16 shrink-0 text-xs">User</span>
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{service.username}</code>
          </div>
        )}

        {/* Password */}
        {service.password && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-16 shrink-0 text-xs">Password</span>
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              {showPw ? service.password : "••••••••"}
            </code>
            <button
              onClick={() => setShowPw(!showPw)}
              className="text-muted-foreground hover:text-foreground"
            >
              {showPw ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            </button>
          </div>
        )}

        {/* Access Token */}
        {service.access_token && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-16 shrink-0 text-xs">Token</span>
            <code className="max-w-[180px] truncate rounded bg-muted px-1.5 py-0.5 text-xs">
              {showToken ? service.access_token : "••••••••"}
            </code>
            <button
              onClick={() => setShowToken(!showToken)}
              className="text-muted-foreground hover:text-foreground"
            >
              {showToken ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

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

      {/* Service Cards */}
      {services.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">
          No services deployed yet.
        </div>
      ) : (
        <div>
          <h3 className="mb-3 text-sm font-semibold">Deployed Services</h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {services.map((svc) => (
              <ServiceCard key={svc.id} service={svc} />
            ))}
          </div>
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
