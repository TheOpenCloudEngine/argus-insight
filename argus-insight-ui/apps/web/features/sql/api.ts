import { authFetch } from "@/features/auth/auth-fetch"
import type {
  AutocompleteData,
  CatalogNode,
  ColumnNode,
  Datasource,
  DatasourceCreate,
  DatasourceTestResult,
  QueryCancelResult,
  QueryExplainResult,
  QueryHistoryItem,
  QueryResult,
  QueryStatusResult,
  QuerySubmitResult,
  SavedQuery,
  SchemaNode,
  TableNode,
} from "./types"

const BASE = "/api/v1/sql"

// ---------------------------------------------------------------------------
// Datasources
// ---------------------------------------------------------------------------

export async function fetchDatasources(): Promise<Datasource[]> {
  const res = await authFetch(`${BASE}/datasources`)
  if (!res.ok) throw new Error(`Failed to fetch datasources: ${res.status}`)
  return res.json()
}

export async function createDatasource(data: DatasourceCreate): Promise<Datasource> {
  const res = await authFetch(`${BASE}/datasources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to create datasource: ${res.status}`)
  return res.json()
}

export async function updateDatasource(
  id: number,
  data: Partial<DatasourceCreate>,
): Promise<Datasource> {
  const res = await authFetch(`${BASE}/datasources/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to update datasource: ${res.status}`)
  return res.json()
}

export async function deleteDatasource(id: number): Promise<void> {
  const res = await authFetch(`${BASE}/datasources/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete datasource: ${res.status}`)
}

export async function testDatasourceConnection(
  data: DatasourceCreate,
): Promise<DatasourceTestResult> {
  const res = await authFetch(`${BASE}/datasources/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      engine_type: data.engine_type,
      host: data.host,
      port: data.port,
      database_name: data.database_name || "",
      username: data.username || "",
      password: data.password || "",
      extra_params: data.extra_params || null,
    }),
  })
  if (!res.ok) throw new Error(`Connection test failed: ${res.status}`)
  return res.json()
}

export async function testExistingDatasource(id: number): Promise<DatasourceTestResult> {
  const res = await authFetch(`${BASE}/datasources/${id}/test`, { method: "POST" })
  if (!res.ok) throw new Error(`Connection test failed: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Metadata browsing
// ---------------------------------------------------------------------------

export async function fetchCatalogs(dsId: number): Promise<CatalogNode[]> {
  const res = await authFetch(`${BASE}/datasources/${dsId}/catalogs`)
  if (!res.ok) throw new Error(`Failed to fetch catalogs: ${res.status}`)
  return res.json()
}

export async function fetchSchemas(dsId: number, catalog = ""): Promise<SchemaNode[]> {
  const q = catalog ? `?catalog=${encodeURIComponent(catalog)}` : ""
  const res = await authFetch(`${BASE}/datasources/${dsId}/schemas${q}`)
  if (!res.ok) throw new Error(`Failed to fetch schemas: ${res.status}`)
  return res.json()
}

export async function fetchTables(
  dsId: number,
  catalog = "",
  schema = "",
): Promise<TableNode[]> {
  const params = new URLSearchParams()
  if (catalog) params.set("catalog", catalog)
  if (schema) params.set("schema", schema)
  const q = params.toString() ? `?${params}` : ""
  const res = await authFetch(`${BASE}/datasources/${dsId}/tables${q}`)
  if (!res.ok) throw new Error(`Failed to fetch tables: ${res.status}`)
  return res.json()
}

export async function fetchColumns(
  dsId: number,
  table: string,
  catalog = "",
  schema = "",
): Promise<ColumnNode[]> {
  const params = new URLSearchParams()
  if (catalog) params.set("catalog", catalog)
  if (schema) params.set("schema", schema)
  const q = params.toString() ? `?${params}` : ""
  const res = await authFetch(
    `${BASE}/datasources/${dsId}/tables/${encodeURIComponent(table)}/columns${q}`,
  )
  if (!res.ok) throw new Error(`Failed to fetch columns: ${res.status}`)
  return res.json()
}

export async function fetchTablePreview(
  dsId: number,
  table: string,
  catalog = "",
  schema = "",
  limit = 100,
): Promise<{ columns: { name: string; data_type: string }[]; rows: unknown[][]; total_rows: number }> {
  const params = new URLSearchParams()
  if (catalog) params.set("catalog", catalog)
  if (schema) params.set("schema", schema)
  params.set("limit", String(limit))
  const res = await authFetch(
    `${BASE}/datasources/${dsId}/tables/${encodeURIComponent(table)}/preview?${params}`,
  )
  if (!res.ok) throw new Error(`Failed to fetch preview: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Autocomplete
// ---------------------------------------------------------------------------

export async function fetchAutocomplete(
  dsId: number,
  catalog = "",
  schema = "",
): Promise<AutocompleteData> {
  const params = new URLSearchParams()
  if (catalog) params.set("catalog", catalog)
  if (schema) params.set("schema", schema)
  const res = await authFetch(`${BASE}/datasources/${dsId}/autocomplete?${params}`)
  if (!res.ok) throw new Error(`Failed to fetch autocomplete: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Query execution
// ---------------------------------------------------------------------------

export async function executeQuery(
  datasourceId: number,
  sql: string,
  maxRows = 1000,
  timeoutSeconds = 300,
): Promise<QueryResult> {
  const res = await authFetch(`${BASE}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      datasource_id: datasourceId,
      sql,
      max_rows: maxRows,
      timeout_seconds: timeoutSeconds,
    }),
  })
  if (!res.ok) throw new Error(`Query execution failed: ${res.status}`)
  return res.json()
}

export async function submitQuery(
  datasourceId: number,
  sql: string,
  maxRows = 1000,
  timeoutSeconds = 300,
): Promise<QuerySubmitResult> {
  const res = await authFetch(`${BASE}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      datasource_id: datasourceId,
      sql,
      max_rows: maxRows,
      timeout_seconds: timeoutSeconds,
    }),
  })
  if (!res.ok) throw new Error(`Query submit failed: ${res.status}`)
  return res.json()
}

export async function fetchExecutionStatus(executionId: string): Promise<QueryStatusResult> {
  const res = await authFetch(`${BASE}/executions/${executionId}/status`)
  if (!res.ok) throw new Error(`Failed to fetch status: ${res.status}`)
  return res.json()
}

export async function fetchExecutionResult(executionId: string): Promise<QueryResult> {
  const res = await authFetch(`${BASE}/executions/${executionId}/result`)
  if (!res.ok) throw new Error(`Failed to fetch result: ${res.status}`)
  return res.json()
}

export async function cancelExecution(executionId: string): Promise<QueryCancelResult> {
  const res = await authFetch(`${BASE}/executions/${executionId}/cancel`, { method: "POST" })
  if (!res.ok) throw new Error(`Failed to cancel: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Explain
// ---------------------------------------------------------------------------

export async function explainQuery(
  datasourceId: number,
  sql: string,
  analyze = false,
): Promise<QueryExplainResult> {
  const res = await authFetch(`${BASE}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ datasource_id: datasourceId, sql, analyze }),
  })
  if (!res.ok) throw new Error(`Explain failed: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

export async function fetchQueryHistory(params?: {
  page?: number
  pageSize?: number
  datasourceId?: number
  status?: string
  search?: string
}): Promise<{ items: QueryHistoryItem[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams()
  if (params?.page) q.set("page", String(params.page))
  if (params?.pageSize) q.set("page_size", String(params.pageSize))
  if (params?.datasourceId) q.set("datasource_id", String(params.datasourceId))
  if (params?.status) q.set("status", params.status)
  if (params?.search) q.set("search", params.search)
  const res = await authFetch(`${BASE}/history?${q}`)
  if (!res.ok) throw new Error(`Failed to fetch history: ${res.status}`)
  return res.json()
}

export async function deleteQueryHistory(id: number): Promise<void> {
  const res = await authFetch(`${BASE}/history/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete history: ${res.status}`)
}

// ---------------------------------------------------------------------------
// Saved queries
// ---------------------------------------------------------------------------

export async function fetchSavedQueries(params?: {
  folder?: string
  datasourceId?: number
}): Promise<{ items: SavedQuery[]; total: number }> {
  const q = new URLSearchParams()
  if (params?.folder) q.set("folder", params.folder)
  if (params?.datasourceId) q.set("datasource_id", String(params.datasourceId))
  const res = await authFetch(`${BASE}/saved-queries?${q}`)
  if (!res.ok) throw new Error(`Failed to fetch saved queries: ${res.status}`)
  return res.json()
}

export async function createSavedQuery(data: {
  name: string
  folder?: string
  datasource_id: number
  sql_text: string
  description?: string
  shared?: string
}): Promise<SavedQuery> {
  const res = await authFetch(`${BASE}/saved-queries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to save query: ${res.status}`)
  return res.json()
}

export async function updateSavedQuery(
  id: number,
  data: Partial<{ name: string; folder: string; sql_text: string; description: string; shared: string }>,
): Promise<SavedQuery> {
  const res = await authFetch(`${BASE}/saved-queries/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to update saved query: ${res.status}`)
  return res.json()
}

export async function deleteSavedQuery(id: number): Promise<void> {
  const res = await authFetch(`${BASE}/saved-queries/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete saved query: ${res.status}`)
}
