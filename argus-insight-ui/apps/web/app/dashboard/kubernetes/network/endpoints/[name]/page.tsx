import { ResourceDetailPage } from "@/features/kubernetes"

export default async function EndpointsDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="endpoints" name={decodeURIComponent(name)} />
}
