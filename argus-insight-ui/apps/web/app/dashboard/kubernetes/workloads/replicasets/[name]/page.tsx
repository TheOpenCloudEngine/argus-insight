import { ResourceDetailPage } from "@/features/kubernetes"

export default async function ReplicaSetDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="replicasets" name={decodeURIComponent(name)} />
}
