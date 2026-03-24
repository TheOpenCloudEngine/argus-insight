/**
 * API client for argus-rag-server.
 * All requests go through Next.js middleware proxy → backend.
 */

const BASE = "/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Stats ---
export const fetchStats = () => apiFetch<DashboardStats>("/stats");

// --- Collections ---
export const fetchCollections = () =>
  apiFetch<Collection[]>("/collections");

export const fetchCollection = (id: number) =>
  apiFetch<Collection>(`/collections/${id}`);

export const createCollection = (data: CollectionCreate) =>
  apiFetch<Collection>("/collections", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateCollection = (id: number, data: Partial<CollectionCreate>) =>
  apiFetch<Collection>(`/collections/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteCollection = (id: number) =>
  apiFetch<void>(`/collections/${id}`, { method: "DELETE" });

// --- Documents ---
export const fetchDocuments = (collId: number, limit = 50, offset = 0) =>
  apiFetch<{ documents: Document[]; total: number }>(
    `/collections/${collId}/documents?limit=${limit}&offset=${offset}`
  );

export const ingestDocument = (collId: number, data: DocumentCreate) =>
  apiFetch<Document>(`/collections/${collId}/documents`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const bulkIngest = (collId: number, documents: DocumentCreate[]) =>
  apiFetch<{ ingested: number; errors: number }>(
    `/collections/${collId}/documents/bulk`,
    { method: "POST", body: JSON.stringify({ documents }) }
  );

// --- Search ---
export const searchHybrid = (params: SearchParams) => {
  const query = new URLSearchParams({ q: params.q });
  if (params.collection_ids) query.set("collection_ids", params.collection_ids);
  if (params.limit) query.set("limit", String(params.limit));
  if (params.threshold) query.set("threshold", String(params.threshold));
  if (params.keyword_weight) query.set("keyword_weight", String(params.keyword_weight));
  if (params.semantic_weight) query.set("semantic_weight", String(params.semantic_weight));
  return apiFetch<SearchResult>(`/search/hybrid?${query.toString()}`);
};

export const searchSemantic = (q: string, collIds?: string, limit = 20) => {
  const query = new URLSearchParams({ q, limit: String(limit) });
  if (collIds) query.set("collection_ids", collIds);
  return apiFetch<SearchResult>(`/search/semantic?${query.toString()}`);
};

// --- Embedding ---
export const embedCollection = (collId: number) =>
  apiFetch<EmbedResult>(`/search/collections/${collId}/embed`, { method: "POST" });

export const clearEmbeddings = (collId: number) =>
  apiFetch<{ cleared: number }>(`/search/collections/${collId}/embeddings`, {
    method: "DELETE",
  });

export const fetchEmbeddingStats = (collId: number) =>
  apiFetch<EmbeddingStats>(`/search/collections/${collId}/stats`);

// --- Data Sources ---
export const fetchSources = (collId: number) =>
  apiFetch<DataSource[]>(`/collections/${collId}/sources`);

export const createSource = (collId: number, data: DataSourceCreate) =>
  apiFetch<DataSource>(`/collections/${collId}/sources`, {
    method: "POST",
    body: JSON.stringify(data),
  });

// --- Sync ---
export const triggerSync = (sourceId: number) =>
  apiFetch<SyncResult>(`/sync/sources/${sourceId}`, { method: "POST" });

export const triggerCollectionSync = (collId: number) =>
  apiFetch<{ syncs: SyncResult[] }>(`/sync/collections/${collId}`, { method: "POST" });

// --- Jobs ---
export const fetchJobs = (collId: number, limit = 20) =>
  apiFetch<SyncJob[]>(`/collections/${collId}/jobs?limit=${limit}`);

// --- Settings ---
export const fetchEmbeddingSettings = () =>
  apiFetch<EmbeddingSettings>("/settings/embedding");

export const updateEmbeddingSettings = (data: EmbeddingSettingsUpdate) =>
  apiFetch<EmbeddingSettings>("/settings/embedding", {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const fetchChunkingSettings = () =>
  apiFetch<ChunkingSettings>("/settings/chunking");

export const updateChunkingSettings = (data: ChunkingSettings) =>
  apiFetch<ChunkingSettings>("/settings/chunking", {
    method: "PUT",
    body: JSON.stringify(data),
  });

// --- Types ---
export interface DashboardStats {
  total_collections: number;
  total_documents: number;
  total_chunks: number;
  embedded_chunks: number;
  coverage_pct: number;
  embedding_provider: string | null;
  embedding_model: string | null;
  recent_jobs: SyncJob[];
}

export interface Collection {
  id: number;
  name: string;
  description: string | null;
  embedding_model: string;
  embedding_dimension: number;
  chunk_strategy: string;
  chunk_max_size: number;
  chunk_overlap: number;
  document_count: number;
  chunk_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CollectionCreate {
  name: string;
  description?: string;
  embedding_model?: string;
  embedding_dimension?: number;
  chunk_strategy?: string;
  chunk_max_size?: number;
  chunk_overlap?: number;
}

export interface Document {
  id: number;
  collection_id: number;
  external_id: string;
  title: string | null;
  source_text: string;
  chunk_count: number;
  is_embedded: string;
  created_at: string;
}

export interface DocumentCreate {
  external_id: string;
  title?: string;
  source_text: string;
  source_type?: string;
}

export interface SearchParams {
  q: string;
  collection_ids?: string;
  limit?: number;
  threshold?: number;
  keyword_weight?: number;
  semantic_weight?: number;
}

export interface SearchResult {
  query: string;
  results: SearchHit[];
  total: number;
}

export interface SearchHit {
  chunk_id?: number;
  document_id: number;
  collection_id: number;
  collection_name: string;
  title: string | null;
  external_id: string;
  chunk_text: string;
  similarity: number;
  match_type: string;
}

export interface DataSource {
  id: number;
  collection_id: number;
  name: string;
  source_type: string;
  sync_mode: string;
  status: string;
  last_sync_at: string | null;
  created_at: string;
}

export interface DataSourceCreate {
  name: string;
  source_type: string;
  config_json?: string;
  sync_mode?: string;
}

export interface SyncJob {
  id: number;
  collection_id: number;
  job_type: string;
  status: string;
  total_items: number;
  processed_items: number;
  error_items: number;
  started_at: string;
  finished_at: string | null;
}

export interface SyncResult {
  job_id: number;
  total: number;
  processed: number;
  errors: number;
  duration_ms: number;
}

export interface EmbedResult {
  total: number;
  processed: number;
  errors: number;
  duration_ms: number;
}

export interface EmbeddingStats {
  total_chunks: number;
  embedded_chunks: number;
  coverage_pct: number;
  provider: string | null;
  model: string | null;
}

export interface EmbeddingSettings {
  provider: string;
  model: string;
  api_url: string;
  dimension: number;
}

export interface EmbeddingSettingsUpdate {
  provider: string;
  model: string;
  api_key?: string;
  api_url?: string;
}

export interface ChunkingSettings {
  default_strategy: string;
  max_chunk_size: number;
  min_chunk_size: number;
  overlap: number;
}
