import { DashboardHeader } from "@/components/dashboard-header"
import { ServiceConfiguration } from "@/features/configuration/components/service-configuration"

export default function ConfigurationPage() {
  return (
    <>
      <DashboardHeader title="Service Configuration" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <ServiceConfiguration />
      </div>
    </>
  )
}
