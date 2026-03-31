import { ResourceDetailPage } from "@/features/kubernetes"

export default async function PVCDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="persistentvolumeclaims" name={decodeURIComponent(name)} />
}
