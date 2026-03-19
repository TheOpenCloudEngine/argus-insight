"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { UCSchemaB } from "@/features/unity-catalog/components/uc-schema-browser"

export default function UnityCatalogLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <DashboardHeader title="Catalog" />
      <div className="flex min-h-0 flex-1">
        <div className="w-64 shrink-0 overflow-y-auto py-4 pl-2">
          <UCSchemaB />
        </div>
        <div className="min-w-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}
