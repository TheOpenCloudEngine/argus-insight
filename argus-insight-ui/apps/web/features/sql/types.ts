// ---------------------------------------------------------------------------
// Datasource
// ---------------------------------------------------------------------------

export type EngineType = "trino" | "starrocks" | "postgresql"

export interface Datasource {
  id: number
  name: string
  engine_type: EngineType
  host: string
  port: number
  database_name: string
  username: string
  extra_params: Record<string, string>
  description: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface DatasourceCreate {
  name: string
  engine_type: EngineType
  host: string
  port: number
  database_name?: string
  username?: string
  password?: string
  extra_params?: Record<string, string>
  description?: string
}

export interface DatasourceTestResult {
  success: boolean
  message: string
  latency_ms: number | null
}

// ---------------------------------------------------------------------------
// Metadata tree
// ---------------------------------------------------------------------------

export interface CatalogNode {
  name: string
}

export interface SchemaNode {
  name: string
  catalog: string
}

export interface TableNode {
  name: string
  table_type: string
  catalog: string
  schema_name: string
}

export interface ColumnNode {
  name: string
  data_type: string
  nullable: boolean
  comment: string
  ordinal_position: number
}

// ---------------------------------------------------------------------------
// Query execution
// ---------------------------------------------------------------------------

export type QueryStatus = "QUEUED" | "RUNNING" | "FINISHED" | "FAILED" | "CANCELLED"

export interface QueryResultColumn {
  name: string
  data_type: string
}

export interface QueryResult {
  execution_id: string
  status: QueryStatus
  columns: QueryResultColumn[]
  rows: unknown[][]
  row_count: number
  elapsed_ms: number
  error_message: string | null
  has_more: boolean
}

export interface QuerySubmitResult {
  execution_id: string
  status: QueryStatus
}

export interface QueryStatusResult {
  execution_id: string
  status: QueryStatus
  row_count: number | null
  elapsed_ms: number | null
  error_message: string | null
  engine_query_id: string | null
}

export interface QueryCancelResult {
  execution_id: string
  status: QueryStatus
  message: string
}

export interface QueryExplainResult {
  plan_text: string
  engine_type: EngineType
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

export interface QueryHistoryItem {
  id: number
  datasource_id: number
  datasource_name: string
  engine_type: string
  sql_text: string
  status: string
  row_count: number | null
  elapsed_ms: number | null
  error_message: string | null
  executed_by: string
  executed_at: string
}

// ---------------------------------------------------------------------------
// Saved queries
// ---------------------------------------------------------------------------

export interface SavedQuery {
  id: number
  name: string
  folder: string
  datasource_id: number
  sql_text: string
  description: string
  shared: string
  created_by: string
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Autocomplete
// ---------------------------------------------------------------------------

export interface AutocompleteData {
  keywords: string[]
  functions: string[]
  data_types: string[]
  tables: string[]
  columns: string[]
}

// ---------------------------------------------------------------------------
// Editor tab
// ---------------------------------------------------------------------------

export interface EditorTab {
  id: string
  title: string
  sql: string
  datasourceId: number | null
  result: QueryResult | null
  status: QueryStatus | null
  executionId: string | null
}
