import { ResourceDetailPage } from "@/features/kubernetes"

export default async function JobDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="jobs" name={decodeURIComponent(name)} />
}
