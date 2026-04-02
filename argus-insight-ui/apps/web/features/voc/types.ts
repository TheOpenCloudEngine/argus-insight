export type VocCategory =
  | "resource_request"
  | "service_issue"
  | "feature_request"
  | "account"
  | "general"

export type VocPriority = "critical" | "high" | "medium" | "low"

export type VocStatus = "open" | "in_progress" | "resolved" | "rejected" | "closed"

export interface VocIssue {
  id: number
  title: string
  description: string
  category: VocCategory
  priority: VocPriority
  status: VocStatus
  author_user_id: number
  author_username: string | null
  assignee_user_id: number | null
  assignee_username: string | null
  workspace_id: number | null
  workspace_name: string | null
  service_id: number | null
  service_name: string | null
  resource_detail: Record<string, unknown> | null
  comment_count: number
  resolved_at: string | null
  closed_at: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedVocIssues {
  items: VocIssue[]
  total: number
  page: number
  page_size: number
}

export interface VocComment {
  id: number
  issue_id: number
  parent_id: number | null
  author_user_id: number
  author_username: string | null
  body: string
  body_plain: string | null
  is_system: boolean
  is_deleted: boolean
  created_at: string
  updated_at: string
}

export interface VocDashboard {
  total: number
  by_status: Record<string, number>
  by_category: Record<string, number>
  by_priority: Record<string, number>
  avg_resolution_hours: number | null
}
