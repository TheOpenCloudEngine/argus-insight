export interface WorkspaceStatItem {
  id: number
  name: string
  display_name: string
  status: string
  service_count: number
  cpu_used: number
  memory_used_gb: number
}

export interface RecentVocItem {
  id: number
  title: string
  category: string
  priority: string
  status: string
  workspace_name: string | null
  author_username: string | null
  created_at: string
}

export interface RecentActivityItem {
  action: string
  actor_username: string | null
  workspace_name: string | null
  detail: Record<string, unknown> | null
  created_at: string
}

export interface AdminDashboard {
  workspaces_total: number
  workspaces_active: number
  users_total: number
  users_active: number
  services_total: number
  services_running: number
  voc_open: number
  voc_critical: number

  cluster_cpu_used: number
  cluster_cpu_limit: number
  cluster_memory_used_gb: number
  cluster_memory_limit_gb: number
  cluster_storage_gb: number

  workspace_stats: WorkspaceStatItem[]

  voc_by_status: Record<string, number>
  voc_by_category: Record<string, number>
  voc_by_priority: Record<string, number>

  recent_voc: RecentVocItem[]
  recent_activity: RecentActivityItem[]
}
