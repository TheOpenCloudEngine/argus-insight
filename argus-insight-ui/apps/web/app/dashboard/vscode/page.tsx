import { DashboardHeader } from "@/components/dashboard-header"
import { VscodeLauncher } from "@/features/vscode/components/vscode-launcher"

export default function VscodePage() {
  return (
    <>
      <DashboardHeader title="VS Code" />
      <div className="flex flex-1 flex-col p-4">
        <VscodeLauncher />
      </div>
    </>
  )
}
