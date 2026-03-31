import { ResourceDetailPage } from "@/features/kubernetes"

export default async function StatefulSetDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="statefulsets" name={decodeURIComponent(name)} />
}
