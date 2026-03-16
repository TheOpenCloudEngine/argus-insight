"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { ServersProvider } from "@/features/servers/components/servers-provider"
import { ServersTableWrapper } from "@/features/servers/components/servers-table-wrapper"

export default function ServerManagementPage() {
  return (
    <ServersProvider>
      <DashboardHeader title="Server Management" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <ServersTableWrapper />
      </div>
    </ServersProvider>
  )
}
