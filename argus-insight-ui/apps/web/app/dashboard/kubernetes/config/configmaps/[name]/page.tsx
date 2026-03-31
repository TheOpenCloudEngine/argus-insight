import { ResourceDetailPage } from "@/features/kubernetes"

export default async function ConfigMapDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="configmaps" name={decodeURIComponent(name)} />
}
