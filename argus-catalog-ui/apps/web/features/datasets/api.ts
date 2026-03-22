/**
 * Dataset API client.
 */

import type { DatasetDetail, DatasetSummary, Platform, SchemaField } from "./data/schema"
import { authFetch } from "@/features/auth/auth-fetch" // Added for SSO AUTH

const BASE = "/api/v1/catalog"

type DatasetListParams = {
  search?: string
  platform?: string
  origin?: string
  tag?: string
  status?: string
  page?: number
  pageSize?: number
}

export type PaginatedDatasets = {
  items: DatasetSummary[]
  total: number
  page: number
  page_size: number
}

export async function fetchDatasets(
  params?: DatasetListParams
): Promise<PaginatedDatasets> {
  const query = new URLSearchParams()
  if (params?.search) query.set("search", params.search)
  if (params?.platform) query.set("platform", params.platform)
  if (params?.origin) query.set("origin", params.origin)
  if (params?.tag) query.set("tag", params.tag)
  if (params?.status) query.set("status", params.status)
  query.set("page", String(params?.page ?? 1))
  query.set("page_size", String(params?.pageSize ?? 20))

  const res = await authFetch(`${BASE}/datasets?${query.toString()}`)
  if (!res.ok) throw new Error(`Failed to fetch datasets: ${res.status}`)
  return res.json()
}

export async function fetchDataset(id: number): Promise<DatasetDetail> {
  const res = await authFetch(`${BASE}/datasets/${id}`)
  if (!res.ok) throw new Error(`Failed to fetch dataset: ${res.status}`)
  return res.json()
}

export async function createDataset(payload: {
  name: string
  platform_id: number
  description?: string
  origin?: string
  qualified_name?: string
  schema_fields?: {
    field_path: string
    field_type: string
    native_type?: string
    description?: string
    nullable?: string
    ordinal?: number
  }[]
  tags?: number[]
  owners?: { owner_name: string; owner_type: string }[]
}): Promise<DatasetDetail> {
  const res = await authFetch(`${BASE}/datasets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to create dataset: ${res.status}`)
  }
  return res.json()
}

export async function updateDataset(
  id: number,
  payload: {
    name?: string
    description?: string
    origin?: string
    qualified_name?: string
    status?: string
  }
): Promise<DatasetDetail> {
  const res = await authFetch(`${BASE}/datasets/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to update dataset: ${res.status}`)
  return res.json()
}

export async function deleteDataset(id: number): Promise<void> {
  const res = await authFetch(`${BASE}/datasets/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete dataset: ${res.status}`)
}

export type PlatformMetadata = {
  platform: Platform
  data_types: { id: number; type_name: string; type_category: string; description: string | null; ordinal: number }[]
  table_types: { id: number; type_name: string; display_name: string; description: string | null; is_default: string; ordinal: number }[]
  storage_formats: { id: number; format_name: string; display_name: string; description: string | null; is_default: string; ordinal: number }[]
  features: { id: number; feature_key: string; display_name: string; description: string | null; value_type: string; is_required: string; ordinal: number }[]
}

export async function fetchPlatformMetadata(platformId: number): Promise<PlatformMetadata> {
  const res = await authFetch(`${BASE}/platforms/${platformId}/metadata`)
  if (!res.ok) throw new Error(`Failed to fetch platform metadata: ${res.status}`)
  return res.json()
}

export async function fetchPlatforms(): Promise<Platform[]> {
  const res = await authFetch(`${BASE}/platforms`)
  if (!res.ok) throw new Error(`Failed to fetch platforms: ${res.status}`)
  return res.json()
}

export async function addDatasetTag(
  datasetId: number,
  tagId: number
): Promise<void> {
  const res = await authFetch(`${BASE}/datasets/${datasetId}/tags/${tagId}`, {
    method: "POST",
  })
  if (!res.ok)
    throw new Error(`Failed to add tag: ${res.status}`)
}

export async function removeDatasetTag(
  datasetId: number,
  tagId: number
): Promise<void> {
  const res = await authFetch(`${BASE}/datasets/${datasetId}/tags/${tagId}`, {
    method: "DELETE",
  })
  if (!res.ok)
    throw new Error(`Failed to remove tag: ${res.status}`)
}

export async function addDatasetOwner(
  datasetId: number,
  payload: { owner_name: string; owner_type: string }
): Promise<void> {
  const res = await authFetch(`${BASE}/datasets/${datasetId}/owners`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok)
    throw new Error(`Failed to add owner: ${res.status}`)
}

export async function removeDatasetOwner(
  datasetId: number,
  ownerId: number
): Promise<void> {
  const res = await authFetch(
    `${BASE}/datasets/${datasetId}/owners/${ownerId}`,
    { method: "DELETE" }
  )
  if (!res.ok)
    throw new Error(`Failed to remove owner: ${res.status}`)
}

export async function updateDatasetSchema(
  datasetId: number,
  fields: {
    field_path: string
    field_type: string
    native_type?: string
    description?: string
    nullable?: string
    ordinal?: number
  }[]
): Promise<SchemaField[]> {
  const res = await authFetch(`${BASE}/datasets/${datasetId}/schema`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  })
  if (!res.ok) throw new Error(`Failed to update schema: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Schema history
// ---------------------------------------------------------------------------

export type SchemaChangeEntry = {
  type: "ADD" | "MODIFY" | "DROP"
  field: string
  before: Record<string, string> | null
  after: Record<string, string> | null
}

export type SchemaSnapshot = {
  id: number
  dataset_id: number
  synced_at: string
  field_count: number
  change_summary: string | null
  changes: SchemaChangeEntry[]
}

export type PaginatedSchemaSnapshots = {
  items: SchemaSnapshot[]
  total: number
  page: number
  page_size: number
}

export async function fetchSchemaHistory(
  datasetId: number,
  page: number = 1,
  pageSize: number = 20,
): Promise<PaginatedSchemaSnapshots> {
  const res = await authFetch(
    `${BASE}/datasets/${datasetId}/schema/history?page=${page}&page_size=${pageSize}`,
  )
  if (!res.ok) throw new Error(`Failed to fetch schema history: ${res.status}`)
  return res.json()
}

export async function addDatasetGlossaryTerm(
  datasetId: number,
  termId: number
): Promise<void> {
  const res = await authFetch(
    `${BASE}/datasets/${datasetId}/glossary/${termId}`,
    { method: "POST" }
  )
  if (!res.ok) throw new Error(`Failed to add glossary term: ${res.status}`)
}

export async function removeDatasetGlossaryTerm(
  datasetId: number,
  termId: number
): Promise<void> {
  const res = await authFetch(
    `${BASE}/datasets/${datasetId}/glossary/${termId}`,
    { method: "DELETE" }
  )
  if (!res.ok)
    throw new Error(`Failed to remove glossary term: ${res.status}`)
}

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

export async function uploadSampleData(
  datasetId: number,
  file: File
): Promise<{ status: string; path: string; size: number }> {
  const form = new FormData()
  form.append("file", file)
  const res = await authFetch(`${BASE}/datasets/${datasetId}/sample`, {
    method: "POST",
    body: form,
  })
  if (!res.ok) throw new Error(`Failed to upload sample data: ${res.status}`)
  return res.json()
}

export async function fetchSampleData(
  datasetId: number
): Promise<Response> {
  return authFetch(`${BASE}/datasets/${datasetId}/sample`)
}

export async function deleteSampleData(
  datasetId: number
): Promise<void> {
  const res = await authFetch(`${BASE}/datasets/${datasetId}/sample`, {
    method: "DELETE",
  })
  if (!res.ok) throw new Error(`Failed to delete sample data: ${res.status}`)
}

export async function convertSampleToParquet(
  datasetId: number,
): Promise<{ status: string; rows: number; columns: number }> {
  const res = await authFetch(`${BASE}/datasets/${datasetId}/sample/convert-to-parquet`, {
    method: "POST",
  })
  if (!res.ok) throw new Error(`Failed to convert to parquet: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Delimiter config
// ---------------------------------------------------------------------------

export type DelimiterConfig = {
  encoding: string
  line_delimiter: string
  delimiter: string
  delimiter_mode: string | null
  delimiter_input: string
  has_header: boolean
  quote_char: string
  custom_quote_char: string
  is_custom_quote: boolean
}

export async function saveDelimiterConfig(
  datasetId: number,
  config: DelimiterConfig
): Promise<void> {
  const res = await authFetch(`${BASE}/datasets/${datasetId}/sample/delimiter`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to save delimiter config: ${res.status}`)
}

export async function fetchDelimiterConfig(
  datasetId: number
): Promise<Response> {
  return authFetch(`${BASE}/datasets/${datasetId}/sample/delimiter`)
}


// ---------------------------------------------------------------------------
// Semantic Search
// ---------------------------------------------------------------------------

export type SemanticSearchResult = {
  dataset: DatasetSummary
  score: number
  match_type: string
}

export type SemanticSearchResponse = {
  items: SemanticSearchResult[]
  total: number
  query: string
  provider: string | null
  model: string | null
}

export async function semanticSearch(
  q: string, limit: number = 20, threshold: number = 0.3,
): Promise<SemanticSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit), threshold: String(threshold) })
  const res = await authFetch(`${BASE}/search/semantic?${params}`)
  if (!res.ok) throw new Error(`Semantic search failed: ${res.status}`)
  return res.json()
}

export async function hybridSearch(
  q: string, limit: number = 20,
  keywordWeight: number = 0.3, semanticWeight: number = 0.7,
): Promise<SemanticSearchResponse> {
  const params = new URLSearchParams({
    q, limit: String(limit),
    keyword_weight: String(keywordWeight), semantic_weight: String(semanticWeight),
  })
  const res = await authFetch(`${BASE}/search/hybrid?${params}`)
  if (!res.ok) throw new Error(`Hybrid search failed: ${res.status}`)
  return res.json()
}
