// ---------------------------------------------------------------------------
// Plugin API response types
// ---------------------------------------------------------------------------

export interface PluginVersionResponse {
  version: string
  display_name: string
  description: string
  status: "stable" | "beta" | "deprecated"
  release_date: string | null
  min_k8s_version: string | null
  changelog: string | null
  upgradeable_from: string[]
  config_schema: JsonSchema | null
}

export interface PluginResponse {
  name: string
  display_name: string
  description: string
  icon: string
  category: string
  depends_on: string[]
  provides: string[]
  requires: string[]
  tags: string[]
  source: "builtin" | "external"
  versions: PluginVersionResponse[]
  default_version: string
  // Admin config (from DB, null if not configured yet)
  enabled: boolean | null
  display_order: number | null
  selected_version: string | null
}

// ---------------------------------------------------------------------------
// Plugin API request types
// ---------------------------------------------------------------------------

export interface PluginOrderItem {
  plugin_name: string
  enabled: boolean
  display_order: number
  selected_version: string | null
  default_config: Record<string, unknown> | null
}

export interface PluginOrderUpdateRequest {
  plugins: PluginOrderItem[]
}

export interface PluginOrderValidateRequest {
  plugin_names: string[]
  versions?: Record<string, string>
}

export interface PluginOrderValidateResponse {
  valid: boolean
  violations: string[]
  suggested_order: string[]
}

export interface PluginRescanResponse {
  total_plugins: number
  new_plugins: string[]
  removed_plugins: string[]
}

// ---------------------------------------------------------------------------
// Workflow execution types (from workspace API)
// ---------------------------------------------------------------------------

export interface StepExecution {
  id: number
  step_name: string
  step_order: number
  status: "pending" | "running" | "completed" | "failed" | "skipped"
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  result_data: string | null
}

export interface WorkflowExecution {
  id: number
  workspace_id: number
  workflow_name: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  created_at: string
  steps: StepExecution[]
}

// ---------------------------------------------------------------------------
// JSON Schema (simplified subset for config form rendering)
// ---------------------------------------------------------------------------

export interface JsonSchemaProperty {
  type?: string
  title?: string
  description?: string
  default?: unknown
  enum?: unknown[]
  minimum?: number
  maximum?: number
  minLength?: number
  maxLength?: number
  items?: JsonSchemaProperty
}

export interface JsonSchema {
  type?: string
  title?: string
  description?: string
  properties?: Record<string, JsonSchemaProperty>
  required?: string[]
}

// ---------------------------------------------------------------------------
// Pipeline types
// ---------------------------------------------------------------------------

export interface PipelineResponse {
  id: number
  name: string
  display_name: string
  description: string | null
  version: number
  created_by: string | null
  plugins: PluginOrderItem[]
  created_at: string
  updated_at: string
}

export interface PipelineListResponse {
  items: PipelineResponse[]
  total: number
}

export interface PipelineCreateRequest {
  name: string
  display_name: string
  description?: string
  created_by?: string
  plugins: PluginOrderItem[]
}

// ---------------------------------------------------------------------------
// Local UI state types
// ---------------------------------------------------------------------------

export interface PipelineStep {
  plugin_name: string
  plugin: PluginResponse
  enabled: boolean
  display_order: number
  selected_version: string
  config: Record<string, unknown>
}
