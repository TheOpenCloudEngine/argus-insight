"use client"

import { useEffect, useState } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Box, FlaskConical, History, Workflow } from "lucide-react"
import { MLStudioWizard } from "@/features/ml-studio/components/ml-studio-wizard"
import { MLStudioExperiments } from "@/features/ml-studio/components/ml-studio-experiments"
import { MLStudioModeler } from "@/features/ml-studio/components/ml-studio-modeler"
import { authFetch } from "@/features/auth/auth-fetch"

interface Workspace {
  id: number
  name: string
  display_name: string
}

export default function MLStudioPage() {
  const [activeTab, setActiveTab] = useState("wizard")
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [selectedWsId, setSelectedWsId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function init() {
      try {
        const res = await authFetch("/api/v1/workspace/workspaces/my")
        if (res.ok) {
          const ws: Workspace[] = await res.json()
          setWorkspaces(ws)

          // If sidebar combo already has a selection, use it
          const stored = sessionStorage.getItem("argus_last_workspace_id")
          if (stored && ws.some((w) => w.id === Number(stored))) {
            setSelectedWsId(Number(stored))
          } else if (ws.length === 1) {
            // Auto-select if only 1 workspace
            setSelectedWsId(ws[0]!.id)
            sessionStorage.setItem("argus_last_workspace_id", String(ws[0]!.id))
            window.dispatchEvent(new CustomEvent("argus:workspace-changed", { detail: { workspaceId: ws[0]!.id } }))
          }
        }
      } catch { /* ignore */ }
      finally { setLoading(false) }
    }
    init()
  }, [])

  const handleWorkspaceChange = (value: string) => {
    const id = Number(value)
    setSelectedWsId(id)
    sessionStorage.setItem("argus_last_workspace_id", String(id))
    // Notify sidebar workspace-switcher
    window.dispatchEvent(new CustomEvent("argus:workspace-changed", { detail: { workspaceId: id } }))
  }

  if (loading) return null

  // Workspace not selected — show selector
  if (!selectedWsId) {
    return (
      <>
        <DashboardHeader title="ML Studio" />
        <div className="flex flex-1 flex-col items-center justify-center p-4">
          <div className="flex flex-col items-center gap-4 max-w-sm text-center">
            <Box className="h-12 w-12 text-muted-foreground/30" />
            <div>
              <h3 className="text-lg font-semibold">Select a Workspace</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Please select a workspace to use ML Studio.
              </p>
            </div>
            {workspaces.length > 0 ? (
              <Select onValueChange={handleWorkspaceChange}>
                <SelectTrigger className="w-64">
                  <SelectValue placeholder="Choose workspace..." />
                </SelectTrigger>
                <SelectContent>
                  {workspaces.map((ws) => (
                    <SelectItem key={ws.id} value={String(ws.id)}>
                      {ws.display_name || ws.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <p className="text-sm text-muted-foreground">
                No workspaces available. Please create one from the Workspaces page.
              </p>
            )}
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <DashboardHeader title="ML Studio" />
      <div className="flex flex-1 flex-col p-4">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-1 flex-col">
          <div className="flex items-center justify-between">
            <TabsList>
              <TabsTrigger value="wizard">
                <FlaskConical className="mr-1.5 h-3.5 w-3.5" />
                Wizard
              </TabsTrigger>
              <TabsTrigger value="modeler">
                <Workflow className="mr-1.5 h-3.5 w-3.5" />
                Modeler
              </TabsTrigger>
              <TabsTrigger value="experiments">
                <History className="mr-1.5 h-3.5 w-3.5" />
                Experiments
              </TabsTrigger>
            </TabsList>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Box className="h-3.5 w-3.5" />
              <Select value={String(selectedWsId)} onValueChange={handleWorkspaceChange}>
                <SelectTrigger className="h-8 w-48 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {workspaces.map((ws) => (
                    <SelectItem key={ws.id} value={String(ws.id)}>
                      {ws.display_name || ws.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <TabsContent value="wizard" className="mt-4 flex flex-1 flex-col">
            <MLStudioWizard />
          </TabsContent>

          <TabsContent value="modeler" className="mt-2 flex flex-1 flex-col">
            <MLStudioModeler onExecuted={() => setActiveTab("experiments")} />
          </TabsContent>

          <TabsContent value="experiments" className="mt-4 flex flex-1 flex-col">
            <MLStudioExperiments />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
