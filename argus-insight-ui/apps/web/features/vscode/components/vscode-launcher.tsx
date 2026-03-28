"use client"

import { useCallback, useEffect, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Play,
  Trash2,
  XCircle,
} from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Badge } from "@workspace/ui/components/badge"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@workspace/ui/components/alert-dialog"
import {
  type DeployStep,
  type VscodeStatus,
  fetchVscodeStatus,
  launchVscode,
  destroyVscode,
  getAuthLaunchUrl,
} from "../api"

const STATUS_BADGE_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  deploying: "secondary",
  running: "default",
  failed: "destructive",
  deleting: "secondary",
  deleted: "outline",
}

function StepIcon({ status }: { status: string }) {
  if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-blue-500 shrink-0" />
  if (status === "failed") return <XCircle className="h-4 w-4 text-red-500 shrink-0" />
  return <div className="h-4 w-4 rounded-full border-2 border-muted shrink-0" />
}

function DeploySteps({ steps }: { steps: DeployStep[] }) {
  if (steps.length === 0) return null

  return (
    <div className="space-y-2 rounded-md border p-3">
      {steps.map((s, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <StepIcon status={s.status} />
          <span className={s.status === "failed" ? "text-red-600 font-medium" : s.status === "running" ? "text-blue-600 font-medium" : "text-muted-foreground"}>
            {s.step}
          </span>
          {s.status === "failed" && s.message && (
            <span className="text-xs text-red-500 truncate max-w-[300px]" title={s.message}>
              — {s.message}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

export function VscodeLauncher() {
  const [status, setStatus] = useState<VscodeStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await fetchVscodeStatus()
      setStatus(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Auto-refresh while deploying or deleting (faster polling for step updates)
  useEffect(() => {
    if (
      status?.exists &&
      (status.status === "deploying" || status.status === "deleting")
    ) {
      const interval = setInterval(refresh, 2000)
      return () => clearInterval(interval)
    }
  }, [status, refresh])

  const handleLaunch = async () => {
    setActionLoading(true)
    setError(null)
    try {
      await launchVscode()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to launch")
    } finally {
      setActionLoading(false)
    }
  }

  const handleDestroy = async () => {
    setActionLoading(true)
    setError(null)
    try {
      await destroyVscode()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to destroy")
    } finally {
      setActionLoading(false)
    }
  }

  const handleOpen = async () => {
    try {
      // Derive backend URL: same hostname as the UI, port 4500
      const backendBase = `${window.location.protocol}//${window.location.hostname}:4500`
      const url = await getAuthLaunchUrl(backendBase)
      // Open backend directly — it sets the cookie and redirects to the app
      window.open(url, "_blank")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open")
    }
  }

  if (loading) {
    return (
      <Card className="max-w-xl">
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  const isDeploying = status?.status === "deploying"
  const isRunning = status?.status === "running"
  const isFailed = status?.status === "failed"
  const isDeleting = status?.status === "deleting"
  const hasInstance = status?.exists && status.status !== "deleted"

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>VS Code Server</CardTitle>
        <CardDescription>
          Your personal VS Code development environment with S3 workspace storage.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {hasInstance && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Status:</span>
              <Badge variant={STATUS_BADGE_VARIANT[status.status ?? ""] ?? "outline"}>
                {isDeploying && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                {isDeleting && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                {status.status}
              </Badge>
            </div>
            {status.hostname && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Hostname:</span>
                <code className="text-sm">{status.hostname}</code>
              </div>
            )}
          </div>
        )}

        {/* Deploy/Destroy steps progress */}
        {hasInstance && status.deploySteps.length > 0 && (isDeploying || isDeleting || isFailed) && (
          <DeploySteps steps={status.deploySteps} />
        )}

        <div className="flex gap-2 pt-2">
          {!hasInstance && (
            <Button onClick={handleLaunch} disabled={actionLoading}>
              {actionLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Launch VS Code
            </Button>
          )}

          {isRunning && (
            <>
              <Button onClick={handleOpen}>
                <ExternalLink className="mr-2 h-4 w-4" />
                Open VS Code
              </Button>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" disabled={actionLoading}>
                    {actionLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="mr-2 h-4 w-4" />
                    )}
                    Destroy
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Destroy VS Code Server?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will remove your VS Code Server instance. Your files
                      in the S3 bucket will be preserved.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={handleDestroy}>
                      Destroy
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </>
          )}

          {isFailed && (
            <Button onClick={handleLaunch} disabled={actionLoading}>
              {actionLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Retry
            </Button>
          )}

          {isDeleting && (
            <p className="text-sm text-muted-foreground pt-2">
              Destroying your VS Code Server...
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
