/**
 * Kubernetes resource types for the dashboard.
 */

export interface ResourceCount {
  total: number
  ready: number
  not_ready: number
  warning: number
}

export interface ClusterInfo {
  version: string
  platform: string
  node_count: number
  namespace_count: number
  connected: boolean
  error: string
}

export interface ClusterOverview {
  cluster: ClusterInfo
  nodes: ResourceCount
  pods: ResourceCount
  deployments: ResourceCount
  services: ResourceCount
  statefulsets: ResourceCount
  daemonsets: ResourceCount
  jobs: ResourceCount
  cronjobs: ResourceCount
  namespaces: string[]
  recent_events: K8sEvent[]
}

export interface NamespaceOverview {
  namespace: string
  pods: ResourceCount
  deployments: ResourceCount
  services: ResourceCount
  statefulsets: ResourceCount
  daemonsets: ResourceCount
  jobs: ResourceCount
  recent_events: K8sEvent[]
}

export interface K8sResourceList {
  kind: string
  api_version: string
  items: K8sResourceItem[]
  total: number
}

export interface K8sResourceItem {
  kind?: string
  apiVersion?: string
  metadata: K8sMetadata
  spec?: Record<string, unknown>
  status?: Record<string, unknown>
  data?: Record<string, unknown>
  [key: string]: unknown
}

export interface K8sMetadata {
  name: string
  namespace?: string
  uid?: string
  creationTimestamp?: string
  labels?: Record<string, string>
  annotations?: Record<string, string>
  ownerReferences?: OwnerReference[]
  resourceVersion?: string
  [key: string]: unknown
}

export interface OwnerReference {
  apiVersion: string
  kind: string
  name: string
  uid: string
}

export interface K8sEvent {
  name: string
  namespace: string
  type: string
  reason: string
  message: string
  source: string
  involved_kind: string
  involved_name: string
  first_timestamp: string
  last_timestamp: string
  count: number
}

export interface WatchEvent {
  type: "ADDED" | "MODIFIED" | "DELETED"
  object: K8sResourceItem
}

export interface PodLogLine {
  line: string
}

export type K8sResourceCategory =
  | "workloads"
  | "network"
  | "storage"
  | "config"
  | "cluster"
