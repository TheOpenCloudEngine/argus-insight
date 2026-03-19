/**
 * Unity Catalog API client.
 *
 * Communicates with the Unity Catalog server REST API.
 * Falls back to mock data when the API is not available.
 */

import {
  mockCatalogs,
  mockSchemas,
  mockTables,
  mockVolumes,
  mockFunctions,
  mockModels,
  mockModelVersions,
} from "./data/mock"
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
// Catalogs
// --------------------------------------------------------------------------- //

export async function listCatalogs(): Promise<Catalog[]> {
  try {
    const data = await apiFetch<{ catalogs: Catalog[] }>("/catalogs")
    return data.catalogs
  } catch {
    return mockCatalogs
  }
}

export async function getCatalog(name: string): Promise<Catalog> {
  try {
    return await apiFetch<Catalog>(`/catalogs/${name}`)
  } catch {
    const found = mockCatalogs.find((c) => c.name === name)
    if (!found) throw new Error(`Catalog '${name}' not found`)
    return found
  }
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
  try {
    const data = await apiFetch<{ schemas: Schema[] }>(`/schemas?catalog_name=${catalogName}`)
    return data.schemas
  } catch {
    return mockSchemas.filter((s) => s.catalog_name === catalogName)
  }
}

export async function getSchema(fullName: string): Promise<Schema> {
  try {
    return await apiFetch<Schema>(`/schemas/${fullName}`)
  } catch {
    const found = mockSchemas.find((s) => s.full_name === fullName)
    if (!found) throw new Error(`Schema '${fullName}' not found`)
    return found
  }
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
  try {
    const data = await apiFetch<{ tables: UCTable[] }>(`/tables?catalog_name=${catalogName}&schema_name=${schemaName}`)
    return data.tables
  } catch {
    return mockTables.filter((t) => t.catalog_name === catalogName && t.schema_name === schemaName)
  }
}

export async function getTable(fullName: string): Promise<UCTable> {
  try {
    return await apiFetch<UCTable>(`/tables/${fullName}`)
  } catch {
    const [cat, sch, tbl] = fullName.split(".")
    const found = mockTables.find((t) => t.catalog_name === cat && t.schema_name === sch && t.name === tbl)
    if (!found) throw new Error(`Table '${fullName}' not found`)
    return found
  }
}

export async function deleteTable(fullName: string): Promise<void> {
  await apiFetch(`/tables/${fullName}`, { method: "DELETE" })
}

// --------------------------------------------------------------------------- //
// Volumes
// --------------------------------------------------------------------------- //

export async function listVolumes(catalogName: string, schemaName: string): Promise<Volume[]> {
  try {
    const data = await apiFetch<{ volumes: Volume[] }>(`/volumes?catalog_name=${catalogName}&schema_name=${schemaName}`)
    return data.volumes
  } catch {
    return mockVolumes.filter((v) => v.catalog_name === catalogName && v.schema_name === schemaName)
  }
}

export async function getVolume(fullName: string): Promise<Volume> {
  try {
    return await apiFetch<Volume>(`/volumes/${fullName}`)
  } catch {
    const [cat, sch, vol] = fullName.split(".")
    const found = mockVolumes.find((v) => v.catalog_name === cat && v.schema_name === sch && v.name === vol)
    if (!found) throw new Error(`Volume '${fullName}' not found`)
    return found
  }
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
  try {
    const data = await apiFetch<{ functions: UCFunction[] }>(`/functions?catalog_name=${catalogName}&schema_name=${schemaName}`)
    return data.functions
  } catch {
    return mockFunctions.filter((f) => f.catalog_name === catalogName && f.schema_name === schemaName)
  }
}

export async function getFunction(fullName: string): Promise<UCFunction> {
  try {
    return await apiFetch<UCFunction>(`/functions/${fullName}`)
  } catch {
    const [cat, sch, fn] = fullName.split(".")
    const found = mockFunctions.find((f) => f.catalog_name === cat && f.schema_name === sch && f.name === fn)
    if (!found) throw new Error(`Function '${fullName}' not found`)
    return found
  }
}

export async function deleteFunction(fullName: string): Promise<void> {
  await apiFetch(`/functions/${fullName}`, { method: "DELETE" })
}

// --------------------------------------------------------------------------- //
// Models
// --------------------------------------------------------------------------- //

export async function listModels(catalogName: string, schemaName: string): Promise<Model[]> {
  try {
    const data = await apiFetch<{ registered_models: Model[] }>(`/models?catalog_name=${catalogName}&schema_name=${schemaName}`)
    return data.registered_models
  } catch {
    return mockModels.filter((m) => m.catalog_name === catalogName && m.schema_name === schemaName)
  }
}

export async function getModel(fullName: string): Promise<Model> {
  try {
    return await apiFetch<Model>(`/models/${fullName}`)
  } catch {
    const [cat, sch, mdl] = fullName.split(".")
    const found = mockModels.find((m) => m.catalog_name === cat && m.schema_name === sch && m.name === mdl)
    if (!found) throw new Error(`Model '${fullName}' not found`)
    return found
  }
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
  try {
    const data = await apiFetch<{ model_versions: ModelVersion[] }>(`/models/${fullModelName}/versions`)
    return data.model_versions
  } catch {
    const [cat, sch, mdl] = fullModelName.split(".")
    return mockModelVersions.filter((v) => v.catalog_name === cat && v.schema_name === sch && v.model_name === mdl)
  }
}

export async function getModelVersion(fullModelName: string, version: number): Promise<ModelVersion> {
  try {
    return await apiFetch<ModelVersion>(`/models/${fullModelName}/versions/${version}`)
  } catch {
    const [cat, sch, mdl] = fullModelName.split(".")
    const found = mockModelVersions.find((v) => v.catalog_name === cat && v.schema_name === sch && v.model_name === mdl && v.version === version)
    if (!found) throw new Error(`Model version '${fullModelName}' v${version} not found`)
    return found
  }
}

export async function updateModelVersion(fullModelName: string, version: number, payload: { comment?: string }): Promise<ModelVersion> {
  return apiFetch<ModelVersion>(`/models/${fullModelName}/versions/${version}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}
