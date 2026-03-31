import { ResourceDetailPage } from "@/features/kubernetes"

export default async function CronJobDetailPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  return <ResourceDetailPage resourceType="cronjobs" name={decodeURIComponent(name)} />
}
