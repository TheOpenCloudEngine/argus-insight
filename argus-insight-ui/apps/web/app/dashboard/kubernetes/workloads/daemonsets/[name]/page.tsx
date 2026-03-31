import { ResourceDetailPage } from "@/features/kubernetes"

export default async function DaemonSetDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="daemonsets" name={decodeURIComponent(name)} />
}
