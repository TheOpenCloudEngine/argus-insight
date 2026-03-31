import { ResourceDetailPage } from "@/features/kubernetes"

export default async function StorageClassDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="storageclasses" name={decodeURIComponent(name)} />
}
