"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { DatasetsDialogs } from "@/features/datasets/components/datasets-dialogs"
import { DatasetsProvider } from "@/features/datasets/components/datasets-provider"
import { DatasetsSmartSearch } from "@/features/datasets/components/datasets-semantic-search"
import { DatasetsTableWrapper } from "@/features/datasets/components/datasets-table-wrapper"

export default function DatasetsPage() {
  return (
    <DatasetsProvider>
      <DashboardHeader title="Datasets" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <DatasetsSmartSearch />
        <DatasetsTableWrapper />
      </div>
      <DatasetsDialogs />
    </DatasetsProvider>
  )
}
