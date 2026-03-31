/**
 * Declarative resource definitions for the K8s dashboard.
 *
 * Each resource type defines its columns, detail tabs, and category.
 * The generic table and detail components use these definitions to
 * render any K8s resource type without resource-specific code.
 */
import type { K8sResourceItem } from "../types"

export type ColumnRender = "text" | "age" | "status-badge" | "labels" | "link" | "custom"

export interface ColumnDef {
  header: string
  accessor: string | ((item: K8sResourceItem) => string | number | null)
  render?: ColumnRender
  className?: string
  width?: string
}

export type DetailTab =
  | "overview"
  | "pods"
  | "containers"
  | "events"
  | "logs"
  | "yaml"
  | "data"
  | "rules"
  | "conditions"
  | "volumes"

export interface ResourceDef {
  kind: string
  apiVersion: string
  namespaced: boolean
  category: string
  plural: string
  singularLabel: string
  pluralLabel: string
  columns: ColumnDef[]
  detailTabs: DetailTab[]
  defaultSort?: string
}

// ── Helper extractors ────────────────────────────────────────────

function getPodStatus(item: K8sResourceItem): string {
  const phase = (item.status as Record<string, unknown>)?.phase as string || ""
  const containerStatuses = (item.status as Record<string, unknown>)?.containerStatuses as Array<Record<string, unknown>> | undefined
  if (containerStatuses) {
    const waiting = containerStatuses.find(
      (cs) => (cs.state as Record<string, unknown>)?.waiting,
    )
    if (waiting) {
      const reason = ((waiting.state as Record<string, unknown>)?.waiting as Record<string, unknown>)?.reason as string
      return reason || "Waiting"
    }
  }
  return phase
}

function getPodRestarts(item: K8sResourceItem): number {
  const containerStatuses = (item.status as Record<string, unknown>)?.containerStatuses as Array<Record<string, unknown>> | undefined
  if (!containerStatuses?.length) return 0
  return containerStatuses.reduce(
    (sum, cs) => sum + ((cs.restartCount as number) || 0),
    0,
  )
}

function getDeployReady(item: K8sResourceItem): string {
  const spec = item.spec as Record<string, unknown> | undefined
  const status = item.status as Record<string, unknown> | undefined
  const desired = (spec?.replicas as number) ?? 0
  const ready = (status?.readyReplicas as number) ?? 0
  return `${ready}/${desired}`
}

function getStsReady(item: K8sResourceItem): string {
  const spec = item.spec as Record<string, unknown> | undefined
  const status = item.status as Record<string, unknown> | undefined
  const desired = (spec?.replicas as number) ?? 0
  const ready = (status?.readyReplicas as number) ?? 0
  return `${ready}/${desired}`
}

function getDsReady(item: K8sResourceItem): string {
  const status = item.status as Record<string, unknown> | undefined
  const desired = (status?.desiredNumberScheduled as number) ?? 0
  const ready = (status?.numberReady as number) ?? 0
  return `${ready}/${desired}`
}

function getJobCompletions(item: K8sResourceItem): string {
  const spec = item.spec as Record<string, unknown> | undefined
  const status = item.status as Record<string, unknown> | undefined
  const completions = (spec?.completions as number) ?? 1
  const succeeded = (status?.succeeded as number) ?? 0
  return `${succeeded}/${completions}`
}

function getServiceType(item: K8sResourceItem): string {
  return (item.spec as Record<string, unknown>)?.type as string || "ClusterIP"
}

function getServiceClusterIP(item: K8sResourceItem): string {
  return (item.spec as Record<string, unknown>)?.clusterIP as string || ""
}

function getServicePorts(item: K8sResourceItem): string {
  const ports = (item.spec as Record<string, unknown>)?.ports as Array<Record<string, unknown>> | undefined
  if (!ports?.length) return ""
  return ports
    .map((p) => {
      const port = p.port
      const proto = p.protocol || "TCP"
      const targetPort = p.targetPort
      return `${port}${targetPort && targetPort !== port ? `:${targetPort}` : ""}/${proto}`
    })
    .join(", ")
}

function getIngressHosts(item: K8sResourceItem): string {
  const rules = (item.spec as Record<string, unknown>)?.rules as Array<Record<string, unknown>> | undefined
  if (!rules?.length) return ""
  return rules.map((r) => r.host as string || "*").join(", ")
}

function getNodeStatus(item: K8sResourceItem): string {
  const conditions = (item.status as Record<string, unknown>)?.conditions as Array<Record<string, unknown>> | undefined
  if (!conditions) return "Unknown"
  const ready = conditions.find((c) => c.type === "Ready")
  return ready?.status === "True" ? "Ready" : "NotReady"
}

function getNodeRoles(item: K8sResourceItem): string {
  const labels = item.metadata.labels || {}
  const roles: string[] = []
  for (const [key] of Object.entries(labels)) {
    if (key.startsWith("node-role.kubernetes.io/")) {
      roles.push(key.replace("node-role.kubernetes.io/", ""))
    }
  }
  return roles.join(", ") || "worker"
}

function getNodeVersion(item: K8sResourceItem): string {
  const nodeInfo = (item.status as Record<string, unknown>)?.nodeInfo as Record<string, unknown> | undefined
  return (nodeInfo?.kubeletVersion as string) || ""
}

function getPvcStatus(item: K8sResourceItem): string {
  return (item.status as Record<string, unknown>)?.phase as string || ""
}

function getPvcCapacity(item: K8sResourceItem): string {
  const status = item.status as Record<string, unknown> | undefined
  const capacity = status?.capacity as Record<string, string> | undefined
  return capacity?.storage || ""
}

function getPvcStorageClass(item: K8sResourceItem): string {
  return (item.spec as Record<string, unknown>)?.storageClassName as string || ""
}

function getPvCapacity(item: K8sResourceItem): string {
  const capacity = (item.spec as Record<string, unknown>)?.capacity as Record<string, string> | undefined
  return capacity?.storage || ""
}

function getPvReclaimPolicy(item: K8sResourceItem): string {
  return (item.spec as Record<string, unknown>)?.persistentVolumeReclaimPolicy as string || ""
}

function getPvStatus(item: K8sResourceItem): string {
  return (item.status as Record<string, unknown>)?.phase as string || ""
}

function getScProvisioner(item: K8sResourceItem): string {
  return (item as Record<string, unknown>).provisioner as string || ""
}

function getScReclaimPolicy(item: K8sResourceItem): string {
  return (item as Record<string, unknown>).reclaimPolicy as string || ""
}

function getConfigMapDataCount(item: K8sResourceItem): number {
  const data = item.data as Record<string, unknown> | undefined
  return data ? Object.keys(data).length : 0
}

function getSecretType(item: K8sResourceItem): string {
  return (item as Record<string, unknown>).type as string || "Opaque"
}

function getSecretDataCount(item: K8sResourceItem): number {
  const data = item.data as Record<string, unknown> | undefined
  return data ? Object.keys(data).length : 0
}

function getCronJobSchedule(item: K8sResourceItem): string {
  return (item.spec as Record<string, unknown>)?.schedule as string || ""
}

function getCronJobLastSchedule(item: K8sResourceItem): string {
  return (item.status as Record<string, unknown>)?.lastScheduleTime as string || ""
}

function getJobStatus(item: K8sResourceItem): string {
  const conditions = (item.status as Record<string, unknown>)?.conditions as Array<Record<string, unknown>> | undefined
  if (!conditions?.length) return "Running"
  const complete = conditions.find((c) => c.type === "Complete" && c.status === "True")
  if (complete) return "Complete"
  const failed = conditions.find((c) => c.type === "Failed" && c.status === "True")
  if (failed) return "Failed"
  return "Running"
}

function getImages(item: K8sResourceItem): string {
  const containers = ((item.spec as Record<string, unknown>)?.template as Record<string, unknown>)?.spec as Record<string, unknown> | undefined
  if (!containers) {
    // Pod directly
    const podContainers = (item.spec as Record<string, unknown>)?.containers as Array<Record<string, unknown>> | undefined
    if (podContainers?.length) {
      return podContainers.map((c) => {
        const img = c.image as string || ""
        return img.split("/").pop() || img
      }).join(", ")
    }
    return ""
  }
  const cs = (containers as Record<string, unknown>)?.containers as Array<Record<string, unknown>> | undefined
  if (!cs?.length) return ""
  return cs.map((c) => {
    const img = c.image as string || ""
    return img.split("/").pop() || img
  }).join(", ")
}

function getEventType(item: K8sResourceItem): string {
  return (item as Record<string, unknown>).type as string || "Normal"
}

function getEventReason(item: K8sResourceItem): string {
  return (item as Record<string, unknown>).reason as string || ""
}

function getEventObject(item: K8sResourceItem): string {
  const obj = (item as Record<string, unknown>).involvedObject as Record<string, unknown> | undefined
  if (!obj) return ""
  return `${obj.kind}/${obj.name}`
}

function getEventMessage(item: K8sResourceItem): string {
  return (item as Record<string, unknown>).message as string || ""
}

function getEventCount(item: K8sResourceItem): number {
  return (item as Record<string, unknown>).count as number || 1
}

function getEventLastSeen(item: K8sResourceItem): string {
  return (item as Record<string, unknown>).lastTimestamp as string || item.metadata.creationTimestamp || ""
}

function getNsStatus(item: K8sResourceItem): string {
  return (item.status as Record<string, unknown>)?.phase as string || ""
}

// ── Resource Definitions ─────────────────────────────────────────

export const RESOURCE_DEFINITIONS: Record<string, ResourceDef> = {
  pods: {
    kind: "Pod",
    apiVersion: "v1",
    namespaced: true,
    category: "workloads",
    plural: "pods",
    singularLabel: "Pod",
    pluralLabel: "Pods",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Status", accessor: getPodStatus, render: "status-badge" },
      { header: "Restarts", accessor: getPodRestarts },
      { header: "Node", accessor: "spec.nodeName" },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "containers", "events", "logs", "yaml"],
  },
  deployments: {
    kind: "Deployment",
    apiVersion: "apps/v1",
    namespaced: true,
    category: "workloads",
    plural: "deployments",
    singularLabel: "Deployment",
    pluralLabel: "Deployments",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Ready", accessor: getDeployReady },
      { header: "Up-to-date", accessor: (i) => ((i.status as Record<string, unknown>)?.updatedReplicas as number) ?? 0 },
      { header: "Available", accessor: (i) => ((i.status as Record<string, unknown>)?.availableReplicas as number) ?? 0 },
      { header: "Images", accessor: getImages },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "pods", "events", "yaml"],
  },
  statefulsets: {
    kind: "StatefulSet",
    apiVersion: "apps/v1",
    namespaced: true,
    category: "workloads",
    plural: "statefulsets",
    singularLabel: "StatefulSet",
    pluralLabel: "StatefulSets",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Ready", accessor: getStsReady },
      { header: "Images", accessor: getImages },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "pods", "events", "yaml"],
  },
  daemonsets: {
    kind: "DaemonSet",
    apiVersion: "apps/v1",
    namespaced: true,
    category: "workloads",
    plural: "daemonsets",
    singularLabel: "DaemonSet",
    pluralLabel: "DaemonSets",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Desired", accessor: (i) => ((i.status as Record<string, unknown>)?.desiredNumberScheduled as number) ?? 0 },
      { header: "Ready", accessor: getDsReady },
      { header: "Node Selector", accessor: (i) => {
        const sel = (i.spec as Record<string, unknown>)?.template as Record<string, unknown>
        const spec = (sel?.spec as Record<string, unknown>)?.nodeSelector as Record<string, string> | undefined
        return spec ? Object.entries(spec).map(([k, v]) => `${k}=${v}`).join(", ") : ""
      }},
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "pods", "events", "yaml"],
  },
  replicasets: {
    kind: "ReplicaSet",
    apiVersion: "apps/v1",
    namespaced: true,
    category: "workloads",
    plural: "replicasets",
    singularLabel: "ReplicaSet",
    pluralLabel: "ReplicaSets",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Desired", accessor: (i) => ((i.spec as Record<string, unknown>)?.replicas as number) ?? 0 },
      { header: "Ready", accessor: (i) => ((i.status as Record<string, unknown>)?.readyReplicas as number) ?? 0 },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "pods", "events", "yaml"],
  },
  jobs: {
    kind: "Job",
    apiVersion: "batch/v1",
    namespaced: true,
    category: "workloads",
    plural: "jobs",
    singularLabel: "Job",
    pluralLabel: "Jobs",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Status", accessor: getJobStatus, render: "status-badge" },
      { header: "Completions", accessor: getJobCompletions },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "pods", "events", "yaml"],
  },
  cronjobs: {
    kind: "CronJob",
    apiVersion: "batch/v1",
    namespaced: true,
    category: "workloads",
    plural: "cronjobs",
    singularLabel: "CronJob",
    pluralLabel: "CronJobs",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Schedule", accessor: getCronJobSchedule },
      { header: "Last Schedule", accessor: getCronJobLastSchedule, render: "age" },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "events", "yaml"],
  },
  services: {
    kind: "Service",
    apiVersion: "v1",
    namespaced: true,
    category: "network",
    plural: "services",
    singularLabel: "Service",
    pluralLabel: "Services",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Type", accessor: getServiceType },
      { header: "Cluster IP", accessor: getServiceClusterIP },
      { header: "Ports", accessor: getServicePorts },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "pods", "events", "yaml"],
  },
  ingresses: {
    kind: "Ingress",
    apiVersion: "networking.k8s.io/v1",
    namespaced: true,
    category: "network",
    plural: "ingresses",
    singularLabel: "Ingress",
    pluralLabel: "Ingresses",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Hosts", accessor: getIngressHosts },
      { header: "Class", accessor: (i) => (i.spec as Record<string, unknown>)?.ingressClassName as string || "" },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "events", "yaml"],
  },
  endpoints: {
    kind: "Endpoints",
    apiVersion: "v1",
    namespaced: true,
    category: "network",
    plural: "endpoints",
    singularLabel: "Endpoints",
    pluralLabel: "Endpoints",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "yaml"],
  },
  persistentvolumeclaims: {
    kind: "PersistentVolumeClaim",
    apiVersion: "v1",
    namespaced: true,
    category: "storage",
    plural: "persistentvolumeclaims",
    singularLabel: "PersistentVolumeClaim",
    pluralLabel: "PersistentVolumeClaims",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Status", accessor: getPvcStatus, render: "status-badge" },
      { header: "Volume", accessor: (i) => (i.spec as Record<string, unknown>)?.volumeName as string || "" },
      { header: "Capacity", accessor: getPvcCapacity },
      { header: "Storage Class", accessor: getPvcStorageClass },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "events", "yaml"],
  },
  persistentvolumes: {
    kind: "PersistentVolume",
    apiVersion: "v1",
    namespaced: false,
    category: "storage",
    plural: "persistentvolumes",
    singularLabel: "PersistentVolume",
    pluralLabel: "PersistentVolumes",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Capacity", accessor: getPvCapacity },
      { header: "Access Modes", accessor: (i) => {
        const modes = (i.spec as Record<string, unknown>)?.accessModes as string[] | undefined
        return modes?.join(", ") || ""
      }},
      { header: "Reclaim Policy", accessor: getPvReclaimPolicy },
      { header: "Status", accessor: getPvStatus, render: "status-badge" },
      { header: "Claim", accessor: (i) => {
        const ref = (i.spec as Record<string, unknown>)?.claimRef as Record<string, unknown> | undefined
        return ref ? `${ref.namespace}/${ref.name}` : ""
      }},
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "events", "yaml"],
  },
  storageclasses: {
    kind: "StorageClass",
    apiVersion: "storage.k8s.io/v1",
    namespaced: false,
    category: "storage",
    plural: "storageclasses",
    singularLabel: "StorageClass",
    pluralLabel: "StorageClasses",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Provisioner", accessor: getScProvisioner },
      { header: "Reclaim Policy", accessor: getScReclaimPolicy },
      { header: "Volume Binding", accessor: (i) => (i as Record<string, unknown>).volumeBindingMode as string || "" },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "yaml"],
  },
  configmaps: {
    kind: "ConfigMap",
    apiVersion: "v1",
    namespaced: true,
    category: "config",
    plural: "configmaps",
    singularLabel: "ConfigMap",
    pluralLabel: "ConfigMaps",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Data", accessor: getConfigMapDataCount },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "data", "yaml"],
  },
  secrets: {
    kind: "Secret",
    apiVersion: "v1",
    namespaced: true,
    category: "config",
    plural: "secrets",
    singularLabel: "Secret",
    pluralLabel: "Secrets",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Namespace", accessor: "metadata.namespace" },
      { header: "Type", accessor: getSecretType },
      { header: "Data", accessor: getSecretDataCount },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "data", "yaml"],
  },
  nodes: {
    kind: "Node",
    apiVersion: "v1",
    namespaced: false,
    category: "cluster",
    plural: "nodes",
    singularLabel: "Node",
    pluralLabel: "Nodes",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Status", accessor: getNodeStatus, render: "status-badge" },
      { header: "Roles", accessor: getNodeRoles },
      { header: "Version", accessor: getNodeVersion },
      { header: "OS Image", accessor: (i) => ((i.status as Record<string, unknown>)?.nodeInfo as Record<string, unknown>)?.osImage as string || "" },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "pods", "conditions", "events", "yaml"],
  },
  namespaces: {
    kind: "Namespace",
    apiVersion: "v1",
    namespaced: false,
    category: "cluster",
    plural: "namespaces",
    singularLabel: "Namespace",
    pluralLabel: "Namespaces",
    columns: [
      { header: "Name", accessor: "metadata.name", render: "link" },
      { header: "Status", accessor: getNsStatus, render: "status-badge" },
      { header: "Age", accessor: "metadata.creationTimestamp", render: "age" },
    ],
    detailTabs: ["overview", "events", "yaml"],
  },
  events: {
    kind: "Event",
    apiVersion: "v1",
    namespaced: true,
    category: "cluster",
    plural: "events",
    singularLabel: "Event",
    pluralLabel: "Events",
    columns: [
      { header: "Type", accessor: getEventType, render: "status-badge" },
      { header: "Reason", accessor: getEventReason },
      { header: "Object", accessor: getEventObject },
      { header: "Message", accessor: getEventMessage, width: "40%" },
      { header: "Count", accessor: getEventCount },
      { header: "Last Seen", accessor: getEventLastSeen, render: "age" },
    ],
    detailTabs: ["overview", "yaml"],
    defaultSort: "lastTimestamp",
  },
}

// ── URL mappings for sidebar navigation ──────────────────────────

export const RESOURCE_URL_MAP: Record<string, string> = {
  pods: "/dashboard/kubernetes/workloads/pods",
  deployments: "/dashboard/kubernetes/workloads/deployments",
  statefulsets: "/dashboard/kubernetes/workloads/statefulsets",
  daemonsets: "/dashboard/kubernetes/workloads/daemonsets",
  replicasets: "/dashboard/kubernetes/workloads/replicasets",
  jobs: "/dashboard/kubernetes/workloads/jobs",
  cronjobs: "/dashboard/kubernetes/workloads/cronjobs",
  services: "/dashboard/kubernetes/network/services",
  ingresses: "/dashboard/kubernetes/network/ingresses",
  endpoints: "/dashboard/kubernetes/network/endpoints",
  persistentvolumeclaims: "/dashboard/kubernetes/storage/pvcs",
  persistentvolumes: "/dashboard/kubernetes/storage/pvs",
  storageclasses: "/dashboard/kubernetes/storage/storageclasses",
  configmaps: "/dashboard/kubernetes/config/configmaps",
  secrets: "/dashboard/kubernetes/config/secrets",
  nodes: "/dashboard/kubernetes/cluster/nodes",
  namespaces: "/dashboard/kubernetes/cluster/namespaces",
  events: "/dashboard/kubernetes/cluster/events",
}

// Reverse: URL slug → resource name
export const URL_SLUG_TO_RESOURCE: Record<string, string> = {
  pods: "pods",
  deployments: "deployments",
  statefulsets: "statefulsets",
  daemonsets: "daemonsets",
  replicasets: "replicasets",
  jobs: "jobs",
  cronjobs: "cronjobs",
  services: "services",
  ingresses: "ingresses",
  endpoints: "endpoints",
  pvcs: "persistentvolumeclaims",
  pvs: "persistentvolumes",
  storageclasses: "storageclasses",
  configmaps: "configmaps",
  secrets: "secrets",
  resourcequotas: "resourcequotas",
  nodes: "nodes",
  namespaces: "namespaces",
  events: "events",
}
