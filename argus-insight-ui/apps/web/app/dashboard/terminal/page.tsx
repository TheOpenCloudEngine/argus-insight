import { DashboardHeader } from "@/components/dashboard-header"
import { TerminalPanel } from "@/features/terminal/components/terminal-panel"

export default function TerminalPage() {
  return (
    <>
      <DashboardHeader title="Terminal" />
      <div className="flex flex-1 flex-col p-4 min-h-0">
        <TerminalPanel />
      </div>
    </>
  )
}
