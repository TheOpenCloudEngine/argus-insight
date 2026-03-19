/**
 * Unity Catalog API client.
 *
 * Communicates with the Unity Catalog server via the argus-insight-server proxy.
 */

import { fetchArgusConfig } from "@/features/settings/api"
import type {
  Catalog,
  Schema,
  UCTable,
  Volume,
  UCFunction,
  Model,
  ModelVersion,
} from "./data/schema"

const BASE = "/api/v1/unity-catalog"

// --------------------------------------------------------------------------- //
// Generic fetch helper
// --------------------------------------------------------------------------- //

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Unity Catalog API error: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

// --------------------------------------------------------------------------- //
// Health check – verify Unity Catalog URL is configured in Settings > Argus
// --------------------------------------------------------------------------- //

export async function checkUcConfigured(): Promise<{ configured: boolean }> {
  const config = await fetchArgusConfig()
  const url = (config.unity_catalog_url ?? "").trim()
  return { configured: url.length > 0 }
}

// --------------------------------------------------------------------------- //
// Catalogs
// --------------------------------------------------------------------------- //

export async function listCatalogs(): Promise<Catalog[]> {
  const data = await apiFetch<{ catalogs: Catalog[] }>("/catalogs")
  return data.catalogs ?? []
}

export async function getCatalog(name: string): Promise<Catalog> {
  return apiFetch<Catalog>(`/catalogs/${name}`)
}

export async function createCatalog(payload: { name: string; comment?: string }): Promise<Catalog> {
  return apiFetch<Catalog>("/catalogs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

export async function updateCatalog(name: string, payload: { comment?: string }): Promise<Catalog> {
  return apiFetch<Catalog>(`/catalogs/${name}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

export async function deleteCatalog(name: string): Promise<void> {
  await apiFetch(`/catalogs/${name}`, { method: "DELETE" })
}

// --------------------------------------------------------------------------- //
// Schemas
// --------------------------------------------------------------------------- //

export async function listSchemas(catalogName: string): Promise<Schema[]> {
  const data = await apiFetch<{ schemas: Schema[] }>(`/schemas?catalog_name=${catalogName}`)
  return data.schemas ?? []
}

export async function getSchema(fullName: string): Promise<Schema> {
  return apiFetch<Schema>(`/schemas/${fullName}`)
}

export async function createSchema(payload: { catalog_name: string; name: string; comment?: string }): Promise<Schema> {
  return apiFetch<Schema>("/schemas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

export async function updateSchema(fullName: string, payload: { comment?: string }): Promise<Schema> {
  return apiFetch<Schema>(`/schemas/${fullName}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

export async function deleteSchema(fullName: string): Promise<void> {
  await apiFetch(`/schemas/${fullName}`, { method: "DELETE" })
}

// --------------------------------------------------------------------------- //
// Tables
// --------------------------------------------------------------------------- //

export async function listTables(catalogName: string, schemaName: string): Promise<UCTable[]> {
  const data = await apiFetch<{ tables: UCTable[] }>(`/tables?catalog_name=${catalogName}&schema_name=${schemaName}`)
  return data.tables ?? []
}

export async function getTable(fullName: string): Promise<UCTable> {
  return apiFetch<UCTable>(`/tables/${fullName}`)
}

export async function deleteTable(fullName: string): Promise<void> {
  await apiFetch(`/tables/${fullName}`, { method: "DELETE" })
}

// --------------------------------------------------------------------------- //
// Volumes
// --------------------------------------------------------------------------- //

export async function listVolumes(catalogName: string, schemaName: string): Promise<Volume[]> {
  const data = await apiFetch<{ volumes: Volume[] }>(`/volumes?catalog_name=${catalogName}&schema_name=${schemaName}`)
  return data.volumes ?? []
}

export async function getVolume(fullName: string): Promise<Volume> {
  return apiFetch<Volume>(`/volumes/${fullName}`)
}

export async function updateVolume(fullName: string, payload: { comment?: string }): Promise<Volume> {
  return apiFetch<Volume>(`/volumes/${fullName}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

export async function deleteVolume(fullName: string): Promise<void> {
  await apiFetch(`/volumes/${fullName}`, { method: "DELETE" })
}

// --------------------------------------------------------------------------- //
// Functions
// --------------------------------------------------------------------------- //

export async function listFunctions(catalogName: string, schemaName: string): Promise<UCFunction[]> {
  const data = await apiFetch<{ functions: UCFunction[] }>(`/functions?catalog_name=${catalogName}&schema_name=${schemaName}`)
  return data.functions ?? []
}

export async function getFunction(fullName: string): Promise<UCFunction> {
  return apiFetch<UCFunction>(`/functions/${fullName}`)
}

export async function deleteFunction(fullName: string): Promise<void> {
  await apiFetch(`/functions/${fullName}`, { method: "DELETE" })
}

// --------------------------------------------------------------------------- //
// Models
// --------------------------------------------------------------------------- //

export async function listModels(catalogName: string, schemaName: string): Promise<Model[]> {
  const data = await apiFetch<{ registered_models: Model[] }>(`/models?catalog_name=${catalogName}&schema_name=${schemaName}`)
  return data.registered_models ?? []
}

export async function getModel(fullName: string): Promise<Model> {
  return apiFetch<Model>(`/models/${fullName}`)
}

export async function updateModel(fullName: string, payload: { comment?: string }): Promise<Model> {
  return apiFetch<Model>(`/models/${fullName}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

export async function deleteModel(fullName: string): Promise<void> {
  await apiFetch(`/models/${fullName}`, { method: "DELETE" })
}

// --------------------------------------------------------------------------- //
// Model Versions
// --------------------------------------------------------------------------- //

export async function listModelVersions(fullModelName: string): Promise<ModelVersion[]> {
  const data = await apiFetch<{ model_versions: ModelVersion[] }>(`/models/${fullModelName}/versions`)
  return data.model_versions ?? []
}

export async function getModelVersion(fullModelName: string, version: number): Promise<ModelVersion> {
  return apiFetch<ModelVersion>(`/models/${fullModelName}/versions/${version}`)
}

export async function updateModelVersion(fullModelName: string, version: number, payload: { comment?: string }): Promise<ModelVersion> {
  return apiFetch<ModelVersion>(`/models/${fullModelName}/versions/${version}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}
