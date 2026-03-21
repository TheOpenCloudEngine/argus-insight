"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { ModelsDialogs } from "@/features/models/components/models-dialogs"
import { ModelsProvider } from "@/features/models/components/models-provider"
import { ModelsTableWrapper } from "@/features/models/components/models-table-wrapper"

export default function ModelsPage() {
  return (
    <ModelsProvider>
      <DashboardHeader title="Models" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <ModelsTableWrapper />
      </div>
      <ModelsDialogs />
    </ModelsProvider>
  )
}
