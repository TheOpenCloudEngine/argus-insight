import { ResourceListPage } from "@/features/kubernetes"

export default function PVCsPage() {
  return <ResourceListPage resourceType="persistentvolumeclaims" title="PersistentVolumeClaims" />
}
