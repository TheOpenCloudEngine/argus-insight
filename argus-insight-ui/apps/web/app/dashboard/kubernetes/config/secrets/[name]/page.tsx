import { ResourceDetailPage } from "@/features/kubernetes"

export default async function SecretDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="secrets" name={decodeURIComponent(name)} />
}
