"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { VocList } from "@/features/voc/components/voc-list"

export default function VocPage() {
  return (
    <>
      <DashboardHeader title="VOC" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <VocList />
      </div>
    </>
  )
}
