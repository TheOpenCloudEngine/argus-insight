import { ResourceDetailPage } from "@/features/kubernetes"

export default async function NamespaceDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="namespaces" name={decodeURIComponent(name)} />
}
