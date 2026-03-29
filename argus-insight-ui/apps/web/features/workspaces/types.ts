export interface WorkspaceResponse {
  id: number
  name: string
  display_name: string
  description: string | null
  domain: string
  k8s_cluster: string | null
  k8s_namespace: string | null
  gitlab_project_id: number | null
  gitlab_project_url: string | null
  minio_endpoint: string | null
  minio_console_endpoint: string | null
  minio_default_bucket: string | null
  airflow_endpoint: string | null
  mlflow_endpoint: string | null
  kserve_endpoint: string | null
  status: "provisioning" | "active" | "failed" | "deleting" | "deleted"
  created_by: number
  created_by_username: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedWorkspaceResponse {
  items: WorkspaceResponse[]
  total: number
  page: number
  page_size: number
}

export interface WorkspacePipeline {
  id: number
  pipeline_id: number
  pipeline_name: string | null
  pipeline_display_name: string | null
  deploy_order: number
  status: string
  created_at: string
}

export interface WorkspaceMember {
  id: number
  workspace_id: number
  user_id: number
  username: string | null
  display_name: string | null
  email: string | null
  role: string
  is_owner: boolean
  gitlab_access_token: string | null
  gitlab_token_name: string | null
  created_at: string
}

export interface WorkspaceCredentials {
  workspace_id: number
  gitlab_http_url: string | null
  gitlab_ssh_url: string | null
  minio_endpoint: string | null
  minio_root_user: string | null
  minio_root_password: string | null
  minio_access_key: string | null
  minio_secret_key: string | null
  airflow_url: string | null
  airflow_admin_username: string | null
  airflow_admin_password: string | null
  mlflow_artifact_bucket: string | null
  kserve_endpoint: string | null
  created_at: string
  updated_at: string
}

export interface WorkspaceService {
  id: number
  workspace_id: number
  plugin_name: string
  display_name: string | null
  version: string | null
  endpoint: string | null
  username: string | null
  password: string | null
  access_token: string | null
  status: string
  metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface AuditLog {
  id: number
  workspace_id: number
  workspace_name: string
  action: string
  target_user_id: number | null
  target_username: string | null
  actor_user_id: number | null
  actor_username: string | null
  detail: Record<string, unknown> | null
  created_at: string
}

export interface PaginatedAuditLogResponse {
  items: AuditLog[]
  total: number
  page: number
  page_size: number
}

export interface WorkflowStep {
  id: number
  step_name: string
  step_order: number
  status: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

export interface WorkflowExecution {
  id: number
  workspace_id: number
  workflow_name: string
  status: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  created_at: string
  steps: WorkflowStep[]
}
