import { DashboardHeader } from "@/components/dashboard-header"
import { ClusterOverview } from "@/features/kubernetes"

export default function KubernetesPage() {
  return (
    <>
      <DashboardHeader title="Kubernetes" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <ClusterOverview />
      </div>
    </>
  )
}
