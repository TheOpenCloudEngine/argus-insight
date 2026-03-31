import { ResourceDetailPage } from "@/features/kubernetes"

export default async function PodDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="pods" name={decodeURIComponent(name)} />
}
