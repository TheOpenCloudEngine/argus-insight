import { z } from "zod"

export const datasetOriginSchema = z.union([
  z.literal("PROD"),
  z.literal("DEV"),
  z.literal("STAGING"),
])
export type DatasetOrigin = z.infer<typeof datasetOriginSchema>

export const datasetStatusSchema = z.union([
  z.literal("active"),
  z.literal("inactive"),
  z.literal("deprecated"),
  z.literal("removed"),
])
export type DatasetStatus = z.infer<typeof datasetStatusSchema>

export const ownerTypeSchema = z.union([
  z.literal("TECHNICAL_OWNER"),
  z.literal("BUSINESS_OWNER"),
  z.literal("DATA_STEWARD"),
])
export type OwnerType = z.infer<typeof ownerTypeSchema>

export const schemaFieldSchema = z.object({
  id: z.number(),
  field_path: z.string(),
  field_type: z.string(),
  native_type: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  nullable: z.string(),
  is_primary_key: z.string().optional().default("false"),
  is_unique: z.string().optional().default("false"),
  is_indexed: z.string().optional().default("false"),
  is_partition_key: z.string().optional().default("false"),
  is_distribution_key: z.string().optional().default("false"),
  ordinal: z.number(),
})
export type SchemaField = z.infer<typeof schemaFieldSchema>

export const tagSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string().nullable().optional(),
  color: z.string(),
  created_at: z.string(),
})
export type Tag = z.infer<typeof tagSchema>

export const glossaryTermSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string().nullable().optional(),
  source: z.string().nullable().optional(),
  parent_id: z.number().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
})
export type GlossaryTerm = z.infer<typeof glossaryTermSchema>

export const ownerSchema = z.object({
  id: z.number(),
  dataset_id: z.number(),
  owner_name: z.string(),
  owner_type: z.string(),
  created_at: z.string(),
})
export type Owner = z.infer<typeof ownerSchema>

export const platformSchema = z.object({
  id: z.number(),
  platform_id: z.string(),
  name: z.string(),
  type: z.string(),
  logo_url: z.string().nullable().optional(),
  created_at: z.string(),
})
export type Platform = z.infer<typeof platformSchema>

export const datasetSummarySchema = z.object({
  id: z.number(),
  urn: z.string(),
  name: z.string(),
  platform_name: z.string(),
  platform_type: z.string(),
  description: z.string().nullable().optional(),
  origin: z.string(),
  status: z.string(),
  is_synced: z.string().optional().default("false"),
  tag_count: z.number(),
  owner_count: z.number(),
  schema_field_count: z.number(),
  created_at: z.coerce.date(),
  updated_at: z.coerce.date(),
})
export type DatasetSummary = z.infer<typeof datasetSummarySchema>

export const datasetPropertySchema = z.object({
  id: z.number(),
  property_key: z.string(),
  property_value: z.string(),
})
export type DatasetProperty = z.infer<typeof datasetPropertySchema>

export const datasetDetailSchema = z.object({
  id: z.number(),
  urn: z.string(),
  name: z.string(),
  platform: platformSchema,
  description: z.string().nullable().optional(),
  origin: z.string(),
  qualified_name: z.string().nullable().optional(),
  table_type: z.string().nullable().optional(),
  storage_format: z.string().nullable().optional(),
  status: z.string(),
  is_synced: z.string().optional().default("false"),
  platform_properties: z.record(z.unknown()).nullable().optional(),
  schema_fields: z.array(schemaFieldSchema),
  tags: z.array(tagSchema),
  owners: z.array(ownerSchema),
  glossary_terms: z.array(glossaryTermSchema),
  properties: z.array(datasetPropertySchema).optional(),
  created_at: z.coerce.date(),
  updated_at: z.coerce.date(),
})
export type DatasetDetail = z.infer<typeof datasetDetailSchema>
