"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { PlaygroundChat } from "@/features/ai-playground/components/playground-chat"

export default function AIPlaygroundPage() {
  return (
    <>
      <DashboardHeader title="AI Playground" />
      <div className="flex flex-1 flex-col p-4">
        <PlaygroundChat />
      </div>
    </>
  )
}
