import { DashboardHeader } from "@/components/dashboard-header"
import { ServiceConfiguration } from "@/features/configuration/components/service-configuration"

export default function ConfigurationPage() {
  return (
    <>
      <DashboardHeader
        title="서비스 설정"
        description="서비스별 구성 파라미터를 조회하고 변경합니다."
      />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <ServiceConfiguration />
      </div>
    </>
  )
}
