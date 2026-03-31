import { ResourceDetailPage } from "@/features/kubernetes"

export default async function ServiceDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="services" name={decodeURIComponent(name)} />
}
