"use client"

import { Suspense } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { WorkspaceOverview } from "@/features/workspaces/components/workspace-overview"

export default function WorkspacePage() {
  return (
    <>
      <DashboardHeader title="Workspace" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Suspense>
          <WorkspaceOverview />
        </Suspense>
      </div>
    </>
  )
}
