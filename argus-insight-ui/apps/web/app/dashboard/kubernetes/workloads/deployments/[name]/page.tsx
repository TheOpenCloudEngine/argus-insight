import { ResourceDetailPage } from "@/features/kubernetes"

export default async function DeploymentDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="deployments" name={decodeURIComponent(name)} />
}
