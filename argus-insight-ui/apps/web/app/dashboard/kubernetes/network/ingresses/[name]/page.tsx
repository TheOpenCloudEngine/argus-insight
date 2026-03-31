import { ResourceDetailPage } from "@/features/kubernetes"

export default async function IngressDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="ingresses" name={decodeURIComponent(name)} />
}
