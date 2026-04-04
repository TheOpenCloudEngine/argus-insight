"use client"

import { useEffect, useState } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { Box } from "lucide-react"
import { SqlProvider } from "@/features/sql/components/sql-provider"
import { SqlWorkspace } from "@/features/sql/components/sql-workspace"
import { authFetch } from "@/features/auth/auth-fetch"

export default function SqlPage() {
  const [wsId, setWsId] = useState<number | null>(null)
  const [hasWorkspaces, setHasWorkspaces] = useState(true)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Read workspace from sessionStorage (set by sidebar workspace-switcher)
    const stored = sessionStorage.getItem("argus_last_workspace_id")
    if (stored) {
      setWsId(Number(stored))
      setLoading(false)
      return
    }

    // No workspace selected — check if any exist
    authFetch("/api/v1/workspace/workspaces/my")
      .then((res) => (res.ok ? res.json() : []))
      .then((ws: { id: number }[]) => {
        if (ws.length === 1) {
          setWsId(ws[0]!.id)
          sessionStorage.setItem("argus_last_workspace_id", String(ws[0]!.id))
        } else if (ws.length === 0) {
          setHasWorkspaces(false)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))

    // Listen for sidebar workspace changes
    const handler = (e: Event) => {
      const id = (e as CustomEvent).detail?.workspaceId
      if (id) setWsId(id)
    }
    window.addEventListener("argus:workspace-changed", handler)
    return () => window.removeEventListener("argus:workspace-changed", handler)
  }, [])

  if (loading) return null

  if (!wsId) {
    return (
      <>
        <DashboardHeader title="SQL" />
        <div className="flex flex-1 flex-col items-center justify-center p-4">
          <div className="flex flex-col items-center gap-4 max-w-sm text-center">
            <Box className="h-12 w-12 text-muted-foreground/30" />
            <div>
              <h3 className="text-lg font-semibold">Select a Workspace</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {hasWorkspaces
                  ? "Please select a workspace from the sidebar first."
                  : "No workspaces available. Please create one from the Workspaces page."}
              </p>
            </div>
          </div>
        </div>
      </>
    )
  }

  return (
    <SqlProvider workspaceId={wsId}>
      <DashboardHeader title="SQL" />
      <div className="flex-1" style={{ height: "calc(100vh - 57px)", overflow: "hidden" }}>
        <SqlWorkspace />
      </div>
    </SqlProvider>
  )
}
