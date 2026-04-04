"use client"

import { use } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { VocDetail } from "@/features/voc/components/voc-detail"

export default function VocDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return (
    <>
      <DashboardHeader title="VOC" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <VocDetail issueId={Number(id)} />
      </div>
    </>
  )
}
