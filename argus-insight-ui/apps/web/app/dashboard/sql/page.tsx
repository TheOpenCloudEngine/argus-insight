"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { SqlProvider } from "@/features/sql/components/sql-provider"
import { SqlWorkspace } from "@/features/sql/components/sql-workspace"

export default function SqlPage() {
  return (
    <SqlProvider>
      <DashboardHeader title="SQL" />
      <div className="flex flex-1 min-h-0">
        <SqlWorkspace />
      </div>
    </SqlProvider>
  )
}
