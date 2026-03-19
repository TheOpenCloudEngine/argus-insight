import { z } from "zod"

export const catalogSchema = z.object({
  id: z.string(),
  name: z.string(),
  comment: z.string().nullable().optional(),
  created_at: z.number().nullable().optional(),
  updated_at: z.number().nullable().optional(),
})

export const schemaSchema = z.object({
  catalog_name: z.string(),
  name: z.string(),
  full_name: z.string(),
  comment: z.string().nullable().optional(),
  created_at: z.number().nullable().optional(),
  updated_at: z.number().nullable().optional(),
})

export const columnSchema = z.object({
  name: z.string(),
  type_name: z.string(),
  type_text: z.string().optional(),
  position: z.number(),
  nullable: z.boolean().optional(),
  comment: z.string().nullable().optional(),
})

export const tableSchema = z.object({
  catalog_name: z.string(),
  schema_name: z.string(),
  name: z.string(),
  table_id: z.string(),
  table_type: z.string().optional(),
  data_source_format: z.string().optional(),
  storage_location: z.string().optional(),
  comment: z.string().nullable().optional(),
  columns: z.array(columnSchema).optional(),
  created_at: z.number().nullable().optional(),
  updated_at: z.number().nullable().optional(),
})

export const volumeSchema = z.object({
  catalog_name: z.string(),
  schema_name: z.string(),
  name: z.string(),
  volume_id: z.string(),
  volume_type: z.string().optional(),
  storage_location: z.string().optional(),
  full_name: z.string().optional(),
  comment: z.string().nullable().optional(),
  created_at: z.number().nullable().optional(),
  updated_at: z.number().nullable().optional(),
})

export const functionParameterSchema = z.object({
  name: z.string(),
  type_name: z.string(),
  type_text: z.string().optional(),
  position: z.number(),
})

export const ucFunctionSchema = z.object({
  catalog_name: z.string(),
  schema_name: z.string(),
  name: z.string(),
  function_id: z.string(),
  input_params: z.object({ parameters: z.array(functionParameterSchema) }).optional(),
  data_type: z.string().optional(),
  full_data_type: z.string().optional(),
  return_params: z.object({ parameters: z.array(functionParameterSchema) }).optional(),
  routine_definition: z.string().optional(),
  external_language: z.string().optional(),
  comment: z.string().nullable().optional(),
  created_at: z.number().nullable().optional(),
  updated_at: z.number().nullable().optional(),
})

export const modelSchema = z.object({
  catalog_name: z.string(),
  schema_name: z.string(),
  name: z.string(),
  model_id: z.string().optional(),
  comment: z.string().nullable().optional(),
  created_at: z.number().nullable().optional(),
  updated_at: z.number().nullable().optional(),
})

export const modelVersionSchema = z.object({
  catalog_name: z.string(),
  schema_name: z.string(),
  model_name: z.string(),
  version: z.number(),
  source: z.string().optional(),
  run_id: z.string().optional(),
  status: z.string().optional(),
  comment: z.string().nullable().optional(),
  created_at: z.number().nullable().optional(),
  updated_at: z.number().nullable().optional(),
})

export type Catalog = z.infer<typeof catalogSchema>
export type Schema = z.infer<typeof schemaSchema>
export type Column = z.infer<typeof columnSchema>
export type UCTable = z.infer<typeof tableSchema>
export type Volume = z.infer<typeof volumeSchema>
export type FunctionParameter = z.infer<typeof functionParameterSchema>
export type UCFunction = z.infer<typeof ucFunctionSchema>
export type Model = z.infer<typeof modelSchema>
export type ModelVersion = z.infer<typeof modelVersionSchema>
