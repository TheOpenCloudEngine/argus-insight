import { ResourceDetailPage } from "@/features/kubernetes"

export default async function NodeDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="nodes" name={decodeURIComponent(name)} />
}
