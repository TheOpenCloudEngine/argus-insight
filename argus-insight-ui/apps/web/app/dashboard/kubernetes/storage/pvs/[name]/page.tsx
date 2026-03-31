import { ResourceDetailPage } from "@/features/kubernetes"

export default async function PVDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="persistentvolumes" name={decodeURIComponent(name)} />
}
