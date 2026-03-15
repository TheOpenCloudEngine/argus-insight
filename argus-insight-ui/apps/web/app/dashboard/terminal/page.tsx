import { DashboardHeader } from "@/components/dashboard-header"
import { TerminalPanel } from "@/features/terminal/components/terminal-panel"

export default function TerminalPage() {
  return (
    <>
      <DashboardHeader title="터미널" description="원격 서버 터미널 접속" />
      <div className="flex flex-1 flex-col p-4 min-h-0">
        <TerminalPanel />
      </div>
    </>
  )
}
