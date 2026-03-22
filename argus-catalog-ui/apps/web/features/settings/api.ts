import { authFetch } from "@/features/auth/auth-fetch" // Added for SSO AUTH

const BASE = "/api/v1/settings"

export type ObjectStorageConfig = {
  endpoint: string
  access_key: string
  secret_key: string
  region: string
  use_ssl: boolean
  bucket: string
  presigned_url_expiry: number
}

export async function fetchObjectStorageConfig(): Promise<ObjectStorageConfig> {
  const res = await authFetch(`${BASE}/object-storage`)
  if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`)
  return res.json()
}

export async function updateObjectStorageConfig(
  config: ObjectStorageConfig,
): Promise<void> {
  const res = await authFetch(`${BASE}/object-storage`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to update config: ${res.status}`)
}

export type InitStep = {
  step: string
  status: "ok" | "skip" | "created" | "error"
  message: string
}

export async function initializeObjectStorage(
  endpoint: string, accessKey: string, secretKey: string, region: string, bucket: string,
): Promise<{ steps: InitStep[] }> {
  const res = await authFetch(`${BASE}/object-storage/initialize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint, access_key: accessKey, secret_key: secretKey, region, bucket }),
  })
  if (!res.ok) throw new Error(`Initialize failed: ${res.status}`)
  return res.json()
}

export async function testObjectStorage(
  endpoint: string,
  accessKey: string,
  secretKey: string,
  region: string,
  bucket: string,
): Promise<{ success: boolean; message: string }> {
  const res = await authFetch(`${BASE}/object-storage/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint,
      access_key: accessKey,
      secret_key: secretKey,
      region,
      bucket,
    }),
  })
  if (!res.ok) throw new Error(`Test failed: ${res.status}`)
  return res.json()
}


// ---------------------------------------------------------------------------
// Embedding configuration
// ---------------------------------------------------------------------------

export type EmbeddingConfig = {
  enabled: boolean
  provider: string
  model: string
  api_key: string
  api_url: string
  dimension: number
}

export async function fetchEmbeddingConfig(): Promise<EmbeddingConfig> {
  const res = await authFetch(`${BASE}/embedding`)
  if (!res.ok) throw new Error(`Failed to fetch embedding config: ${res.status}`)
  return res.json()
}

export async function updateEmbeddingConfig(config: EmbeddingConfig): Promise<void> {
  const res = await authFetch(`${BASE}/embedding`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to update embedding config: ${res.status}`)
}

export async function testEmbedding(
  config: EmbeddingConfig,
): Promise<{ success: boolean; message: string }> {
  const res = await authFetch(`${BASE}/embedding/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Test failed: ${res.status}`)
  return res.json()
}

export type EmbeddingStats = {
  total_datasets: number
  embedded_datasets: number
  coverage_pct: number
  provider: string | null
  model: string | null
  dimension: number | null
}

export async function fetchEmbeddingStats(): Promise<EmbeddingStats> {
  const res = await authFetch("/api/v1/catalog/search/embeddings/stats")
  if (!res.ok) throw new Error(`Failed to fetch stats: ${res.status}`)
  return res.json()
}

export async function backfillEmbeddings(): Promise<{
  total: number; embedded: number; skipped: number; errors: number
}> {
  const res = await authFetch("/api/v1/catalog/search/embeddings/backfill", { method: "POST" })
  if (!res.ok) throw new Error(`Backfill failed: ${res.status}`)
  return res.json()
}

export async function clearEmbeddings(): Promise<{ deleted: number }> {
  const res = await authFetch("/api/v1/catalog/search/embeddings", { method: "DELETE" })
  if (!res.ok) throw new Error(`Clear failed: ${res.status}`)
  return res.json()
}


// ---------------------------------------------------------------------------
// Authentication (Keycloak) configuration
// ---------------------------------------------------------------------------

export type AuthConfig = {
  type: string
  server_url: string
  realm: string
  client_id: string
  client_secret: string
  admin_role: string
  superuser_role: string
  user_role: string
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  const res = await authFetch(`${BASE}/auth`)
  if (!res.ok) throw new Error(`Failed to fetch auth config: ${res.status}`)
  return res.json()
}

export async function fetchAuthSecret(): Promise<string> {
  const res = await authFetch(`${BASE}/auth/secret`)
  if (!res.ok) throw new Error(`Failed to fetch secret: ${res.status}`)
  const data = await res.json()
  return data.client_secret
}

export async function updateAuthConfig(config: AuthConfig): Promise<void> {
  const res = await authFetch(`${BASE}/auth`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to update auth config: ${res.status}`)
}

export type KeycloakInitRequest = {
  server_url: string
  admin_username: string
  admin_password: string
  realm: string
  client_id: string
  client_secret: string
  roles: string[]
}

export async function initializeKeycloak(
  req: KeycloakInitRequest,
): Promise<{ steps: InitStep[] }> {
  const res = await authFetch(`${BASE}/auth/initialize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`Initialize failed: ${res.status}`)
  return res.json()
}

export async function testAuthConnection(
  config: AuthConfig,
): Promise<{ success: boolean; message: string }> {
  const res = await authFetch(`${BASE}/auth/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Test failed: ${res.status}`)
  return res.json()
}


// ---------------------------------------------------------------------------
// CORS configuration
// ---------------------------------------------------------------------------

export type CorsConfig = {
  origins: string
}

export async function fetchCorsConfig(): Promise<CorsConfig> {
  const res = await authFetch(`${BASE}/cors`)
  if (!res.ok) throw new Error(`Failed to fetch CORS config: ${res.status}`)
  return res.json()
}

export async function updateCorsConfig(config: CorsConfig): Promise<void> {
  const res = await authFetch(`${BASE}/cors`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to update CORS config: ${res.status}`)
}

