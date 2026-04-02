"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { AdminDashboardView } from "@/features/dashboard/components/admin-dashboard"

export default function DashboardPage() {
  return (
    <>
      <DashboardHeader title="Dashboard" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <AdminDashboardView />
      </div>
    </>
  )
}
