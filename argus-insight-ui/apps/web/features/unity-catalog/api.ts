/**
 * Unity Catalog API — thin re-exports that delegate to UnityCatalogClient.
 *
 * Existing call-sites keep working unchanged. New code can import ucClient
 * directly from "./uc-client" for the full set of operations.
 */

import { fetchArgusConfig } from "@/features/settings/api"
import { ucClient } from "./uc-client"
import type {
  CreateTablePayload,
  CreateVolumePayload,
  CreateModelPayload,
} from "./uc-client"
import type {
  Catalog,
  Schema,
  UCTable,
  Volume,
  UCFunction,
  Model,
  ModelVersion,
} from "./data/schema"

// Re-export client & payload types for convenience
export { ucClient } from "./uc-client"
export type {
  CreateCatalogPayload,
  UpdateCatalogPayload,
  CreateSchemaPayload,
  UpdateSchemaPayload,
  CreateTablePayload,
  CreateTableColumn,
  CreateVolumePayload,
  UpdateVolumePayload,
  CreateFunctionPayload,
  CreateModelPayload,
  UpdateModelPayload,
  CreateModelVersionPayload,
  UpdateModelVersionPayload,
} from "./uc-client"

// --------------------------------------------------------------------------- //
// Health check
// --------------------------------------------------------------------------- //

export async function checkUcConfigured(): Promise<{ configured: boolean }> {
  const config = await fetchArgusConfig()
  const url = (config.unity_catalog_url ?? "").trim()
  return { configured: url.length > 0 }
}

// --------------------------------------------------------------------------- //
// Catalogs
// --------------------------------------------------------------------------- //

export const listCatalogs = (): Promise<Catalog[]> => ucClient.catalogList()
export const getCatalog = (name: string): Promise<Catalog> => ucClient.catalogGet(name)
export const createCatalog = (payload: { name: string; comment?: string }): Promise<Catalog> => ucClient.catalogCreate(payload)
export const updateCatalog = (name: string, payload: { comment?: string }): Promise<Catalog> => ucClient.catalogUpdate(name, payload)
export const deleteCatalog = (name: string): Promise<void> => ucClient.catalogDelete(name)

// --------------------------------------------------------------------------- //
// Schemas
// --------------------------------------------------------------------------- //

export const listSchemas = (catalogName: string): Promise<Schema[]> => ucClient.schemaList(catalogName)
export const getSchema = (fullName: string): Promise<Schema> => ucClient.schemaGet(fullName)
export const createSchema = (payload: { catalog_name: string; name: string; comment?: string }): Promise<Schema> => ucClient.schemaCreate(payload)
export const updateSchema = (fullName: string, payload: { comment?: string }): Promise<Schema> => ucClient.schemaUpdate(fullName, payload)
export const deleteSchema = (fullName: string): Promise<void> => ucClient.schemaDelete(fullName)

// --------------------------------------------------------------------------- //
// Tables
// --------------------------------------------------------------------------- //

export const listTables = (catalogName: string, schemaName: string): Promise<UCTable[]> => ucClient.tableList(catalogName, schemaName)
export const getTable = (fullName: string): Promise<UCTable> => ucClient.tableGet(fullName)
export const createTable = (payload: CreateTablePayload): Promise<UCTable> => ucClient.tableCreate(payload)
export const deleteTable = (fullName: string): Promise<void> => ucClient.tableDelete(fullName)

// --------------------------------------------------------------------------- //
// Volumes
// --------------------------------------------------------------------------- //

export const listVolumes = (catalogName: string, schemaName: string): Promise<Volume[]> => ucClient.volumeList(catalogName, schemaName)
export const getVolume = (fullName: string): Promise<Volume> => ucClient.volumeGet(fullName)
export const createVolume = (payload: CreateVolumePayload): Promise<Volume> => ucClient.volumeCreate(payload)
export const updateVolume = (fullName: string, payload: { comment?: string }): Promise<Volume> => ucClient.volumeUpdate(fullName, payload)
export const deleteVolume = (fullName: string): Promise<void> => ucClient.volumeDelete(fullName)

// --------------------------------------------------------------------------- //
// Functions
// --------------------------------------------------------------------------- //

export const listFunctions = (catalogName: string, schemaName: string): Promise<UCFunction[]> => ucClient.functionList(catalogName, schemaName)
export const getFunction = (fullName: string): Promise<UCFunction> => ucClient.functionGet(fullName)
export const deleteFunction = (fullName: string): Promise<void> => ucClient.functionDelete(fullName)

// --------------------------------------------------------------------------- //
// Models
// --------------------------------------------------------------------------- //

export const listModels = (catalogName: string, schemaName: string): Promise<Model[]> => ucClient.modelList(catalogName, schemaName)
export const getModel = (fullName: string): Promise<Model> => ucClient.modelGet(fullName)
export const createModel = (payload: CreateModelPayload): Promise<Model> => ucClient.modelCreate(payload)
export const updateModel = (fullName: string, payload: { comment?: string }): Promise<Model> => ucClient.modelUpdate(fullName, payload)
export const deleteModel = (fullName: string): Promise<void> => ucClient.modelDelete(fullName)

// --------------------------------------------------------------------------- //
// Model Versions
// --------------------------------------------------------------------------- //

export const listModelVersions = (fullModelName: string): Promise<ModelVersion[]> => ucClient.modelVersionList(fullModelName)
export const getModelVersion = (fullModelName: string, version: number): Promise<ModelVersion> => ucClient.modelVersionGet(fullModelName, version)
export const updateModelVersion = (fullModelName: string, version: number, payload: { comment?: string }): Promise<ModelVersion> => ucClient.modelVersionUpdate(fullModelName, version, payload)
export const deleteModelVersion = (fullModelName: string, version: number): Promise<void> => ucClient.modelVersionDelete(fullModelName, version)
