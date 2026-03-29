/**
 * UnityCatalogClient — typed client that mirrors the `bin/uc` CLI.
 *
 * CLI reference (unitycatalog/unitycatalog):
 *   bin/uc <entity> <operation> [options]
 *
 * Entities : catalog, schema, table, volume, function, model, model_version
 * Operations: create, list, get, update, delete  (+ read/write for table, finalize for model_version)
 *
 * This client communicates with the Unity Catalog server through the
 * argus-insight-server proxy at /api/v1/unity-catalog/*.
 */

import { authFetch } from "@/features/auth/auth-fetch"
import type {
  Catalog,
  Schema,
  UCTable,
  Volume,
  UCFunction,
  Model,
  ModelVersion,
} from "./data/schema"

// --------------------------------------------------------------------------- //
// Types — payload shapes matching the UC REST API
// --------------------------------------------------------------------------- //

export type CreateCatalogPayload = {
  name: string
  comment?: string
}

export type UpdateCatalogPayload = {
  comment?: string
}

export type CreateSchemaPayload = {
  catalog_name: string
  name: string
  comment?: string
}

export type UpdateSchemaPayload = {
  comment?: string
}

export type CreateTableColumn = {
  name: string
  type_name: string
  position: number
  nullable?: boolean
  comment?: string
}

export type CreateTablePayload = {
  catalog_name: string
  schema_name: string
  name: string
  table_type: string
  data_source_format: string
  columns: CreateTableColumn[]
  storage_location?: string
  properties?: Record<string, string>
  comment?: string
}

export type CreateVolumePayload = {
  catalog_name: string
  schema_name: string
  name: string
  volume_type: string
  storage_location?: string
  comment?: string
}

export type UpdateVolumePayload = {
  comment?: string
}

export type CreateFunctionPayload = {
  catalog_name: string
  schema_name: string
  name: string
  data_type: string
  full_data_type: string
  input_params: { parameters: { name: string; type_name: string; type_text: string; position: number }[] }
  return_params?: { parameters: { name: string; type_name: string; type_text: string; position: number }[] }
  routine_definition: string
  routine_body: string
  parameter_style: string
  is_deterministic: boolean
  sql_data_access: string
  is_null_call: boolean
  security_type: string
  external_language?: string
  comment?: string
}

export type CreateModelPayload = {
  catalog_name: string
  schema_name: string
  name: string
  comment?: string
}

export type UpdateModelPayload = {
  comment?: string
}

export type CreateModelVersionPayload = {
  catalog_name: string
  schema_name: string
  model_name: string
  source: string
  run_id?: string
  comment?: string
}

export type UpdateModelVersionPayload = {
  comment?: string
}

// --------------------------------------------------------------------------- //
// Client class
// --------------------------------------------------------------------------- //

const JSON_HEADERS = { "Content-Type": "application/json" } as const

export class UnityCatalogClient {
  private baseUrl: string

  constructor(baseUrl = "/api/v1/unity-catalog") {
    this.baseUrl = baseUrl
  }

  // ---- generic helpers --------------------------------------------------- //

  private async fetch<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await authFetch(`${this.baseUrl}${path}`, init)
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      const detail = body?.detail ?? `Unity Catalog API error: ${res.status}`
      throw new Error(detail)
    }
    return res.json()
  }

  private post<T>(path: string, body: unknown): Promise<T> {
    return this.fetch<T>(path, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    })
  }

  private patch<T>(path: string, body: unknown): Promise<T> {
    return this.fetch<T>(path, {
      method: "PATCH",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    })
  }

  private delete(path: string): Promise<void> {
    return this.fetch(path, { method: "DELETE" }) as Promise<void>
  }

  // ======================================================================= //
  // Catalogs   — bin/uc catalog <create|list|get|update|delete>
  // ======================================================================= //

  async catalogList(): Promise<Catalog[]> {
    const data = await this.fetch<{ catalogs: Catalog[] }>("/catalogs")
    return data.catalogs ?? []
  }

  catalogGet(name: string): Promise<Catalog> {
    return this.fetch<Catalog>(`/catalogs/${name}`)
  }

  catalogCreate(payload: CreateCatalogPayload): Promise<Catalog> {
    return this.post<Catalog>("/catalogs", payload)
  }

  catalogUpdate(name: string, payload: UpdateCatalogPayload): Promise<Catalog> {
    return this.patch<Catalog>(`/catalogs/${name}`, payload)
  }

  catalogDelete(name: string): Promise<void> {
    return this.delete(`/catalogs/${name}`)
  }

  // ======================================================================= //
  // Schemas   — bin/uc schema <create|list|get|update|delete>
  // ======================================================================= //

  async schemaList(catalogName: string): Promise<Schema[]> {
    const data = await this.fetch<{ schemas: Schema[] }>(`/schemas?catalog_name=${catalogName}`)
    return data.schemas ?? []
  }

  schemaGet(fullName: string): Promise<Schema> {
    return this.fetch<Schema>(`/schemas/${fullName}`)
  }

  schemaCreate(payload: CreateSchemaPayload): Promise<Schema> {
    return this.post<Schema>("/schemas", payload)
  }

  schemaUpdate(fullName: string, payload: UpdateSchemaPayload): Promise<Schema> {
    return this.patch<Schema>(`/schemas/${fullName}`, payload)
  }

  schemaDelete(fullName: string): Promise<void> {
    return this.delete(`/schemas/${fullName}`)
  }

  // ======================================================================= //
  // Tables   — bin/uc table <create|list|get|delete>
  // ======================================================================= //

  async tableList(catalogName: string, schemaName: string): Promise<UCTable[]> {
    const data = await this.fetch<{ tables: UCTable[] }>(
      `/tables?catalog_name=${catalogName}&schema_name=${schemaName}`,
    )
    return data.tables ?? []
  }

  tableGet(fullName: string): Promise<UCTable> {
    return this.fetch<UCTable>(`/tables/${fullName}`)
  }

  tableCreate(payload: CreateTablePayload): Promise<UCTable> {
    return this.post<UCTable>("/tables", payload)
  }

  tableDelete(fullName: string): Promise<void> {
    return this.delete(`/tables/${fullName}`)
  }

  // ======================================================================= //
  // Volumes   — bin/uc volume <create|list|get|update|delete>
  // ======================================================================= //

  async volumeList(catalogName: string, schemaName: string): Promise<Volume[]> {
    const data = await this.fetch<{ volumes: Volume[] }>(
      `/volumes?catalog_name=${catalogName}&schema_name=${schemaName}`,
    )
    return data.volumes ?? []
  }

  volumeGet(fullName: string): Promise<Volume> {
    return this.fetch<Volume>(`/volumes/${fullName}`)
  }

  volumeCreate(payload: CreateVolumePayload): Promise<Volume> {
    return this.post<Volume>("/volumes", payload)
  }

  volumeUpdate(fullName: string, payload: UpdateVolumePayload): Promise<Volume> {
    return this.patch<Volume>(`/volumes/${fullName}`, payload)
  }

  volumeDelete(fullName: string): Promise<void> {
    return this.delete(`/volumes/${fullName}`)
  }

  // ======================================================================= //
  // Functions — bin/uc function <create|list|get|delete>
  // ======================================================================= //

  async functionList(catalogName: string, schemaName: string): Promise<UCFunction[]> {
    const data = await this.fetch<{ functions: UCFunction[] }>(
      `/functions?catalog_name=${catalogName}&schema_name=${schemaName}`,
    )
    return data.functions ?? []
  }

  functionGet(fullName: string): Promise<UCFunction> {
    return this.fetch<UCFunction>(`/functions/${fullName}`)
  }

  functionCreate(payload: CreateFunctionPayload): Promise<UCFunction> {
    return this.post<UCFunction>("/functions", payload)
  }

  functionDelete(fullName: string): Promise<void> {
    return this.delete(`/functions/${fullName}`)
  }

  // ======================================================================= //
  // Models   — bin/uc model <create|list|get|update|delete>
  // ======================================================================= //

  async modelList(catalogName: string, schemaName: string): Promise<Model[]> {
    const data = await this.fetch<{ registered_models: Model[] }>(
      `/models?catalog_name=${catalogName}&schema_name=${schemaName}`,
    )
    return data.registered_models ?? []
  }

  modelGet(fullName: string): Promise<Model> {
    return this.fetch<Model>(`/models/${fullName}`)
  }

  modelCreate(payload: CreateModelPayload): Promise<Model> {
    return this.post<Model>("/models", payload)
  }

  modelUpdate(fullName: string, payload: UpdateModelPayload): Promise<Model> {
    return this.patch<Model>(`/models/${fullName}`, payload)
  }

  modelDelete(fullName: string): Promise<void> {
    return this.delete(`/models/${fullName}`)
  }

  // ======================================================================= //
  // Model Versions — bin/uc model_version <create|list|get|update|delete|finalize>
  // ======================================================================= //

  async modelVersionList(fullModelName: string): Promise<ModelVersion[]> {
    const data = await this.fetch<{ model_versions: ModelVersion[] }>(
      `/models/${fullModelName}/versions`,
    )
    return data.model_versions ?? []
  }

  modelVersionGet(fullModelName: string, version: number): Promise<ModelVersion> {
    return this.fetch<ModelVersion>(`/models/${fullModelName}/versions/${version}`)
  }

  modelVersionCreate(payload: CreateModelVersionPayload): Promise<ModelVersion> {
    return this.post<ModelVersion>(
      `/models/${payload.catalog_name}.${payload.schema_name}.${payload.model_name}/versions`,
      payload,
    )
  }

  modelVersionUpdate(
    fullModelName: string,
    version: number,
    payload: UpdateModelVersionPayload,
  ): Promise<ModelVersion> {
    return this.patch<ModelVersion>(`/models/${fullModelName}/versions/${version}`, payload)
  }

  modelVersionDelete(fullModelName: string, version: number): Promise<void> {
    return this.delete(`/models/${fullModelName}/versions/${version}`)
  }

  modelVersionFinalize(fullModelName: string, version: number): Promise<ModelVersion> {
    return this.post<ModelVersion>(
      `/models/${fullModelName}/versions/${version}/finalize`,
      {},
    )
  }
}

// --------------------------------------------------------------------------- //
// Default singleton instance
// --------------------------------------------------------------------------- //

export const ucClient = new UnityCatalogClient()
