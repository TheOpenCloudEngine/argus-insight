"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { toast } from "sonner"
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  Check,
  ChevronDown,
  Circle,
  Code2,
  Columns3,
  Database,
  FlaskConical,
  Flame,
  Globe,
  History,
  Pencil,
  Plus,
  Rocket,
  Server,
  Settings2,
  Tags,
  Trash2,
  Users,
  Workflow,
  X,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@workspace/ui/components/command"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
// Textarea removed — replaced by Tiptap MarkdownEditor
import { Popover, PopoverContent, PopoverTrigger } from "@workspace/ui/components/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Separator } from "@workspace/ui/components/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { DashboardHeader } from "@/components/dashboard-header"
import {
  addDatasetGlossaryTerm,
  addDatasetOwner,
  addDatasetTag,
  fetchDataset,
  fetchPlatformMetadata,
  type PlatformMetadata,
  removeDatasetGlossaryTerm,
  removeDatasetOwner,
  removeDatasetTag,
  updateDataset,
  updateDatasetSchema,
} from "@/features/datasets/api"
import { fetchTags } from "@/features/tags/api"
import { fetchGlossaryTerms } from "@/features/glossary/api"
import { fetchUsers } from "@/features/users/api"
import type { User } from "@/features/users/data/schema"
import type { DatasetDetail, GlossaryTerm, SchemaField, Tag } from "@/features/datasets/data/schema"
import { SampleDataTab } from "@/features/datasets/components/sample-data-tab"
import { SchemaHistoryTab } from "@/features/datasets/components/schema-history-tab"
import { PlatformSpecificCard } from "@/features/datasets/components/platform-specific-card"
import { MarkdownEditor, MarkdownViewer } from "@/features/datasets/components/markdown-editor"
import { SchemaEditGrid, type EditableField } from "@/features/datasets/components/schema-edit-grid"
import { NiFiFlowTab } from "@/features/datasets/components/nifi-flow-tab"
import { KestraFlowTab } from "@/features/datasets/components/kestra-flow-tab"
import { AirflowDagTab } from "@/features/datasets/components/airflow-dag-tab"

// ---------------------------------------------------------------------------
// Schema field helpers for editing
// ---------------------------------------------------------------------------

let _idCounter = 0
function genId(): string {
  return `f-${Date.now()}-${++_idCounter}-${Math.random().toString(36).slice(2, 8)}`
}

function newField(ordinal: number): EditableField {
  return {
    key: genId(),
    field_path: "",
    field_type: "STRING",
    native_type: "",
    description: "",
    nullable: "true",
    is_primary_key: "false",
    is_unique: "false",
    is_indexed: "false",
    ordinal,
  }
}

function toEditable(f: SchemaField): EditableField {
  return {
    key: genId(),
    field_path: f.field_path,
    field_type: f.field_type,
    native_type: f.native_type ?? "",
    description: f.description ?? "",
    nullable: f.nullable,
    is_primary_key: f.is_primary_key ?? "false",
    is_unique: f.is_unique ?? "false",
    is_indexed: f.is_indexed ?? "false",
    ordinal: f.ordinal,
  }
}

// ---------------------------------------------------------------------------
// Avro schema generator
// ---------------------------------------------------------------------------
function fieldTypeToAvro(fieldType: string): unknown {
  const t = fieldType.toUpperCase()
  switch (t) {
    case "BOOLEAN":
    case "BOOL":
      return "boolean"
    case "TINYINT":
    case "SMALLINT":
    case "INT":
    case "INT8":
    case "INT16":
    case "INT32":
    case "INTEGER":
    case "MEDIUMINT":
    case "SERIAL":
      return "int"
    case "BIGINT":
    case "INT64":
    case "BIGSERIAL":
    case "LARGEINT":
      return "long"
    case "FLOAT":
    case "FLOAT32":
    case "REAL":
      return "float"
    case "DOUBLE":
    case "DOUBLE PRECISION":
    case "FLOAT64":
      return "double"
    case "DECIMAL":
    case "NUMERIC":
    case "NUMBER":
    case "MONEY":
    case "DECIMAL128":
      return { type: "bytes", logicalType: "decimal", precision: 38, scale: 10 }
    case "DATE":
      return { type: "int", logicalType: "date" }
    case "TIME":
      return { type: "long", logicalType: "time-millis" }
    case "TIMESTAMP":
    case "TIMESTAMPTZ":
    case "TIMESTAMP_NTZ":
    case "TIMESTAMP_LTZ":
    case "TIMESTAMP_TZ":
    case "DATETIME":
    case "UNIXTIME_MICROS":
      return { type: "long", logicalType: "timestamp-millis" }
    case "BINARY":
    case "BYTEA":
    case "VARBINARY":
    case "BYTES":
    case "BINDATA":
    case "BLOB":
      return "bytes"
    case "UUID":
      return { type: "string", logicalType: "uuid" }
    case "JSON":
    case "JSONB":
    case "VARIANT":
    case "SUPER":
      return "string"
    case "ARRAY":
      return { type: "array", items: "string" }
    case "MAP":
      return { type: "map", values: "string" }
    case "STRUCT":
    case "ROW":
    case "OBJECT":
      return { type: "record", name: "nested", fields: [] }
    default:
      return "string"
  }
}

function generateAvroSchema(datasetName: string, namespace: string, fields: SchemaField[]): string {
  const avroFields = fields.map((f) => {
    const avroType = fieldTypeToAvro(f.field_type)
    const fieldDef: Record<string, unknown> = {
      name: f.field_path.replace(/[^a-zA-Z0-9_]/g, "_"),
      type: f.nullable === "true" ? ["null", avroType] : avroType,
    }
    if (f.nullable === "true") {
      fieldDef.default = null
    }
    if (f.description) {
      fieldDef.doc = f.description
    }
    return fieldDef
  })

  const schema = {
    type: "record",
    name: datasetName.replace(/[^a-zA-Z0-9_]/g, "_"),
    namespace,
    doc: `Avro schema for ${datasetName}`,
    fields: avroFields,
  }

  return JSON.stringify(schema, null, 2)
}

// ---------------------------------------------------------------------------
// PySpark code generator
// ---------------------------------------------------------------------------

function fieldTypeToSparkType(fieldType: string): string {
  switch (fieldType.toUpperCase()) {
    case "NUMBER": return "StringType()"  // Read as string for safety; cast in downstream
    case "STRING": return "StringType()"
    case "BOOLEAN": return "StringType()"
    case "DATE": return "StringType()"
    case "BYTES": return "BinaryType()"
    case "MAP": return "StringType()"
    case "ARRAY": return "StringType()"
    case "ENUM": return "StringType()"
    default: return "StringType()"
  }
}

function getJdbcUrl(platformType: string): { url: string; driver: string; format: string } {
  switch (platformType) {
    case "mysql":
      return { url: "jdbc:mysql://<HOST>:<PORT>/<DATABASE>", driver: "com.mysql.cj.jdbc.Driver", format: "jdbc" }
    case "postgresql":
      return { url: "jdbc:postgresql://<HOST>:<PORT>/<DATABASE>", driver: "org.postgresql.Driver", format: "jdbc" }
    case "greenplum":
      return { url: "jdbc:postgresql://<HOST>:<PORT>/<DATABASE>", driver: "org.postgresql.Driver", format: "jdbc" }
    case "starrocks":
      return { url: "jdbc:mysql://<HOST>:<PORT>/<DATABASE>", driver: "com.mysql.cj.jdbc.Driver", format: "jdbc" }
    case "trino":
      return { url: "jdbc:trino://<HOST>:<PORT>/<CATALOG>/<SCHEMA>", driver: "io.trino.jdbc.TrinoDriver", format: "jdbc" }
    case "oracle":
      return { url: "jdbc:oracle:thin:@<HOST>:<PORT>:<SID>", driver: "oracle.jdbc.OracleDriver", format: "jdbc" }
    default:
      return { url: `jdbc:${platformType}://<HOST>:<PORT>/<DATABASE>`, driver: "<DRIVER_CLASS>", format: "jdbc" }
  }
}

function generatePySparkCode(dataset: DatasetDetail): string {
  const tableName = dataset.name  // e.g. "sakila.actor"
  const parts = tableName.split(".")
  const dbName = parts.length > 1 ? parts[0] : "<DATABASE>"
  const tblName = parts.length > 1 ? parts[1] : parts[0]
  const platformType = dataset.platform.type
  const platformId = dataset.platform.platform_id
  const jdbc = getJdbcUrl(platformType)
  const fields = dataset.schema_fields

  const structFields = fields.map((f) => {
    const sparkType = fieldTypeToSparkType(f.field_type)
    const nullable = f.nullable === "true" ? "True" : "False"
    return `    StructField("${f.field_path}", ${sparkType}, ${nullable}),`
  }).join("\n")

  return `"""
PySpark code to read '${tableName}' from ${dataset.platform.name} (${platformId})
and write to HDFS as Parquet with optional date-based partitioning.

Generated by Argus Catalog
Platform: ${platformType} (${platformId})
Table: ${dbName}.${tblName}
Fields: ${fields.length}
"""

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, BinaryType,
)

# ---------------------------------------------------------------------------
# 1. Spark Session
# ---------------------------------------------------------------------------

spark = SparkSession.builder \\
    .appName("argus-catalog-${platformId}-${tblName}") \\
    .getOrCreate()

# ---------------------------------------------------------------------------
# 2. Schema Definition (from Argus Catalog metadata)
# ---------------------------------------------------------------------------

schema = StructType([
${structFields}
])

# ---------------------------------------------------------------------------
# 3. Read from Source (JDBC)
# ---------------------------------------------------------------------------

jdbc_url = "${jdbc.url}"

df = spark.read \\
    .format("${jdbc.format}") \\
    .option("url", jdbc_url) \\
    .option("dbtable", "${dbName}.${tblName}") \\
    .option("driver", "${jdbc.driver}") \\
    .option("user", "<USERNAME>") \\
    .option("password", "<PASSWORD>") \\
    .schema(schema) \\
    .load()

print(f"Read {df.count()} rows from ${tableName}")
df.printSchema()

# ---------------------------------------------------------------------------
# 4. Write to HDFS as Parquet
# ---------------------------------------------------------------------------

hdfs_path = "hdfs://nameservice/data/catalog/${platformId}/${dbName}/${tblName}"

df.write \\
    .mode("overwrite") \\
    .parquet(hdfs_path)

print(f"Written to {hdfs_path}")

# ---------------------------------------------------------------------------
# 5. Date-based Partitioning (Optional)
#
# Uncomment and customize the code below to read/write by date partition.
# This is useful for incremental ingestion of large tables.
#
# Requirements:
#   - The source table must have a date/timestamp column (e.g. "last_update")
#   - Adjust the column name, date format, and paths as needed
# ---------------------------------------------------------------------------

# from pyspark.sql.functions import col, to_date, lit
# from datetime import date, timedelta
#
# # Configuration
# DATE_COLUMN = "last_update"          # Column to partition by
# TARGET_DATE = date(2026, 3, 20)      # Specific date to process
# # TARGET_DATE = date.today() - timedelta(days=1)  # Yesterday
#
# # Read only rows matching the target date
# df_daily = spark.read \\
#     .format("${jdbc.format}") \\
#     .option("url", jdbc_url) \\
#     .option("dbtable", f"(SELECT * FROM ${dbName}.${tblName} WHERE DATE({DATE_COLUMN}) = '{TARGET_DATE}') AS t") \\
#     .option("driver", "${jdbc.driver}") \\
#     .option("user", "<USERNAME>") \\
#     .option("password", "<PASSWORD>") \\
#     .schema(schema) \\
#     .load()
#
# # Add partition column
# df_daily = df_daily.withColumn("dt", lit(str(TARGET_DATE)))
#
# # Write with date partitioning (append mode for incremental)
# hdfs_partitioned_path = "hdfs://nameservice/data/catalog/${platformId}/${dbName}/${tblName}"
#
# df_daily.write \\
#     .mode("append") \\
#     .partitionBy("dt") \\
#     .parquet(hdfs_partitioned_path)
#
# print(f"Written {df_daily.count()} rows for {TARGET_DATE} to {hdfs_partitioned_path}/dt={TARGET_DATE}")

# ---------------------------------------------------------------------------
# 6. Cleanup
# ---------------------------------------------------------------------------

spark.stop()
`
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------
export default function DatasetDetailPage() {
  const params = useParams()
  const router = useRouter()
  const datasetId = Number(params.id)
  const [dataset, setDataset] = useState<DatasetDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // All tags / glossary terms for pickers
  const [allTags, setAllTags] = useState<Tag[]>([])
  const [allGlossary, setAllGlossary] = useState<GlossaryTerm[]>([])

  // Platform metadata
  const [platformMeta, setPlatformMeta] = useState<PlatformMetadata | null>(null)

  // Users for owner picker (loaded on search)
  const [ownerSearchUsers, setOwnerSearchUsers] = useState<User[]>([])
  const [ownerSearchQuery, setOwnerSearchQuery] = useState("")
  const [ownerSearching, setOwnerSearching] = useState(false)

  // Popover states
  const [tagPopoverOpen, setTagPopoverOpen] = useState(false)
  const [glossaryPopoverOpen, setGlossaryPopoverOpen] = useState(false)
  const [ownerPopoverOpen, setOwnerPopoverOpen] = useState(false)
  const [ownerType, setOwnerType] = useState("TECHNICAL_OWNER")

  // Schema inline edit state
  const [schemaEditing, setSchemaEditing] = useState(false)
  const [editFields, setEditFields] = useState<EditableField[]>([])
  const [schemaSaving, setSchemaSaving] = useState(false)

  // Status toggling
  const [statusUpdating, setStatusUpdating] = useState(false)

  // Description inline editing
  const [descEditing, setDescEditing] = useState(false)
  const [descDraft, setDescDraft] = useState("")
  const [descSaving, setDescSaving] = useState(false)

  const load = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setIsLoading(true)
      const data = await fetchDataset(datasetId)
      setDataset(data)
      // Fetch platform metadata
      fetchPlatformMetadata(data.platform.id).then(setPlatformMeta).catch(() => {})
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load dataset")
    } finally {
      if (showLoading) setIsLoading(false)
    }
  }, [datasetId])

  useEffect(() => {
    load()
    fetchTags().then(setAllTags).catch(() => {})
    fetchGlossaryTerms().then(setAllGlossary).catch(() => {})
  }, [load])

  // Debounced owner search: fetch users when ownerSearchQuery changes
  useEffect(() => {
    const trimmed = ownerSearchQuery.trim()
    if (!trimmed) {
      setOwnerSearchUsers([])
      return
    }
    setOwnerSearching(true)
    const timer = setTimeout(() => {
      fetchUsers({ search: trimmed, pageSize: 0 })
        .then((r) => setOwnerSearchUsers(r.items))
        .catch(() => setOwnerSearchUsers([]))
        .finally(() => setOwnerSearching(false))
    }, 300)
    return () => clearTimeout(timer)
  }, [ownerSearchQuery])

  // -------------------------------------------------------------------------
  // Status change
  // -------------------------------------------------------------------------
  const handleStatusChange = async (newStatus: string) => {
    if (!dataset || statusUpdating || dataset.status === newStatus) return
    try {
      setStatusUpdating(true)
      const updated = await updateDataset(datasetId, { status: newStatus })
      setDataset(updated)
    } catch {
      // revert silently
    } finally {
      setStatusUpdating(false)
    }
  }

  const statusConfig: { [key: string]: { label: string; icon: React.ReactNode; className: string } } = {
    active: {
      label: "Active",
      icon: <Check className="mr-1.5 h-3.5 w-3.5" />,
      className: "bg-primary text-primary-foreground hover:bg-primary/90",
    },
    inactive: {
      label: "Inactive",
      icon: <Circle className="mr-1.5 h-3.5 w-3.5" />,
      className: "bg-amber-500 text-white hover:bg-amber-500/90",
    },
    deprecated: {
      label: "Deprecated",
      icon: <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />,
      className: "bg-zinc-600 text-white hover:bg-zinc-600/90",
    },
  }

  const allStatuses = ["active", "inactive", "deprecated"] as const
  const currentStatusConfig = statusConfig[dataset?.status ?? "active"] ?? statusConfig["active"]

  // Origin (environment) config & handler
  const [originUpdating, setOriginUpdating] = useState(false)

  const originConfig: { [key: string]: { label: string; icon: React.ReactNode; className: string } } = {
    PROD: {
      label: "PROD",
      icon: <Rocket className="mr-1.5 h-3.5 w-3.5" />,
      className: "bg-emerald-600 text-white hover:bg-emerald-600/90",
    },
    STAGING: {
      label: "STAGING",
      icon: <FlaskConical className="mr-1.5 h-3.5 w-3.5" />,
      className: "bg-orange-500 text-white hover:bg-orange-500/90",
    },
    DEV: {
      label: "DEV",
      icon: <Server className="mr-1.5 h-3.5 w-3.5" />,
      className: "bg-sky-500 text-white hover:bg-sky-500/90",
    },
  }

  const allOrigins = ["PROD", "STAGING", "DEV"] as const
  const currentOriginConfig = originConfig[dataset?.origin ?? "PROD"] ?? originConfig["PROD"]

  const handleOriginChange = async (newOrigin: string) => {
    if (!dataset || originUpdating || dataset.origin === newOrigin) return
    try {
      setOriginUpdating(true)
      const updated = await updateDataset(datasetId, { origin: newOrigin })
      setDataset(updated)
    } catch {
      // revert silently
    } finally {
      setOriginUpdating(false)
    }
  }

  // -------------------------------------------------------------------------
  // Description inline editing
  // -------------------------------------------------------------------------
  const startDescEdit = () => {
    setDescDraft(dataset?.description ?? "")
    setDescEditing(true)
  }

  const cancelDescEdit = () => {
    setDescEditing(false)
    setDescDraft("")
  }

  const saveDesc = async () => {
    if (!dataset) return
    const trimmed = descDraft.trim()
    if (trimmed === (dataset.description ?? "")) {
      setDescEditing(false)
      return
    }
    try {
      setDescSaving(true)
      const updated = await updateDataset(datasetId, { description: trimmed || undefined })
      setDataset(updated)
      setDescEditing(false)
    } catch {
      // keep editing on error
    } finally {
      setDescSaving(false)
    }
  }

  // Keyboard shortcuts removed — Tiptap editor handles its own input.
  // Save/Cancel are done via buttons.
  const _unused_handleDescKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") cancelDescEdit()
    else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) saveDesc()
  }

  // -------------------------------------------------------------------------
  // Schema inline editing
  // -------------------------------------------------------------------------
  const startSchemaEdit = () => {
    if (!dataset) return
    setEditFields(
      dataset.schema_fields.length > 0
        ? dataset.schema_fields.map(toEditable)
        : [newField(0)]
    )
    setSchemaEditing(true)
  }

  const cancelSchemaEdit = () => {
    setSchemaEditing(false)
    setEditFields([])
  }

  const saveSchema = async () => {
    const valid = editFields.filter((f) => f.field_path.trim() && f.field_type.trim())
    const payload = valid.map((f, idx) => ({
      field_path: f.field_path.trim(),
      field_type: f.field_type.trim(),
      native_type: f.native_type.trim() || undefined,
      description: f.description.trim() || undefined,
      nullable: f.nullable,
      is_primary_key: f.is_primary_key,
      is_unique: f.is_unique,
      is_indexed: f.is_indexed,
      ordinal: idx,
    }))
    try {
      setSchemaSaving(true)
      await updateDatasetSchema(datasetId, payload)
      setSchemaEditing(false)
      await load(false)
    } catch {
      // keep editing on error
    } finally {
      setSchemaSaving(false)
    }
  }

  // Platform data type options for the Type dropdown
  const dataTypeOptions = platformMeta?.data_types ?? []
  const featuresMeta = platformMeta?.features ?? []

  // -------------------------------------------------------------------------
  // Tag management
  // -------------------------------------------------------------------------
  const handleAddTag = async (tagId: number) => {
    try {
      await addDatasetTag(datasetId, tagId)
      setTagPopoverOpen(false)
      await load(false)
    } catch {
      // ignore
    }
  }

  const handleRemoveTag = async (tagId: number) => {
    try {
      await removeDatasetTag(datasetId, tagId)
      await load(false)
    } catch {
      // ignore
    }
  }

  // -------------------------------------------------------------------------
  // Glossary management
  // -------------------------------------------------------------------------
  const handleAddGlossary = async (termId: number) => {
    try {
      await addDatasetGlossaryTerm(datasetId, termId)
      setGlossaryPopoverOpen(false)
      await load(false)
    } catch {
      // ignore
    }
  }

  const handleRemoveGlossary = async (termId: number) => {
    try {
      await removeDatasetGlossaryTerm(datasetId, termId)
      await load(false)
    } catch {
      // ignore
    }
  }

  // -------------------------------------------------------------------------
  // Owner management
  // -------------------------------------------------------------------------
  const handleAddOwner = async (user: User) => {
    try {
      const ownerName = `${user.firstName} ${user.lastName}`.trim() || user.username
      await addDatasetOwner(datasetId, {
        owner_name: ownerName,
        owner_type: ownerType,
      })
      setOwnerPopoverOpen(false)
      setOwnerSearchQuery("")
      setOwnerSearchUsers([])
      await load(false)
    } catch {
      // ignore
    }
  }

  const handleRemoveOwner = async (ownerId: number) => {
    try {
      await removeDatasetOwner(datasetId, ownerId)
      await load(false)
    } catch {
      // ignore
    }
  }

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------
  const attachedTagIds = new Set(dataset?.tags.map((t) => t.id) ?? [])
  const availableTags = allTags.filter((t) => !attachedTagIds.has(t.id))

  const attachedTermIds = new Set(dataset?.glossary_terms.map((t) => t.id) ?? [])
  const availableGlossary = allGlossary.filter((t) => !attachedTermIds.has(t.id))

  // Owners: exclude users who are already owners
  const attachedOwnerNames = new Set(dataset?.owners.map((o) => o.owner_name) ?? [])
  const availableUsers = ownerSearchUsers.filter((u) => {
    const fullName = `${u.firstName} ${u.lastName}`.trim() || u.username
    return !attachedOwnerNames.has(fullName)
  })

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (isLoading) {
    return (
      <>
        <DashboardHeader title="Dataset" />
        <div className="flex items-center justify-center p-8">
          <p className="text-muted-foreground">Loading dataset...</p>
        </div>
      </>
    )
  }

  if (error || !dataset) {
    return (
      <>
        <DashboardHeader title="Dataset" />
        <div className="flex flex-col items-center justify-center gap-4 p-8">
          <p className="text-destructive">{error || "Dataset not found"}</p>
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
        </div>
      </>
    )
  }

  return (
    <>
      <DashboardHeader title={dataset.name} />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Back button */}
        <div>
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back
          </Button>
        </div>

        {/* Dataset header info */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <CardTitle className="text-xl flex items-center gap-2">
                  {dataset.name}
                  {dataset.is_synced === "true" && (
                    <span className="inline-flex items-center rounded-full border border-orange-400 px-2 py-0.5 text-[10px] font-semibold text-orange-500">
                      SYNCED
                    </span>
                  )}
                </CardTitle>
                <p className="text-sm text-muted-foreground font-mono">
                  {dataset.urn}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {/* Status dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      size="sm"
                      disabled={statusUpdating}
                      className={currentStatusConfig?.className}
                    >
                      {currentStatusConfig?.icon}
                      {currentStatusConfig?.label}
                      <ChevronDown className="ml-1.5 h-3 w-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {allStatuses
                      .filter((s) => s !== dataset.status)
                      .map((s) => {
                        const cfg = statusConfig[s]
                        return (
                          <DropdownMenuItem
                            key={s}
                            onClick={() => handleStatusChange(s)}
                          >
                            {cfg?.icon}
                            {cfg?.label}
                          </DropdownMenuItem>
                        )
                      })}
                  </DropdownMenuContent>
                </DropdownMenu>
                {/* Origin dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      size="sm"
                      disabled={originUpdating}
                      className={currentOriginConfig?.className}
                    >
                      {currentOriginConfig?.icon}
                      {currentOriginConfig?.label}
                      <ChevronDown className="ml-1.5 h-3 w-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {allOrigins
                      .filter((o) => o !== dataset.origin)
                      .map((o) => {
                        const cfg = originConfig[o]
                        return (
                          <DropdownMenuItem
                            key={o}
                            onClick={() => handleOriginChange(o)}
                          >
                            {cfg?.icon}
                            {cfg?.label}
                          </DropdownMenuItem>
                        )
                      })}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 text-sm">
              <div>
                <span className="text-muted-foreground">Platform</span>
                <div className="flex items-center gap-1.5 mt-1 font-medium">
                  <Database className="h-4 w-4" />
                  {dataset.platform.name}
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Qualified Name</span>
                <p className="mt-1 font-medium">{dataset.qualified_name || "-"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Created</span>
                <p className="mt-1 font-medium">
                  {new Date(dataset.created_at).toLocaleDateString()}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Updated</span>
                <p className="mt-1 font-medium">
                  {new Date(dataset.updated_at).toLocaleDateString()}
                </p>
              </div>
            </div>
            <Separator className="my-4" />
            <div>
              <span className="text-sm text-muted-foreground">Description</span>
              {descEditing ? (
                <div className="mt-1 space-y-2">
                  <MarkdownEditor
                    value={descDraft}
                    onChange={setDescDraft}
                    editable={!descSaving}
                    placeholder="Write description in Markdown..."
                  />
                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={saveDesc} disabled={descSaving}>
                      {descSaving ? "Saving..." : "Save"}
                    </Button>
                    <Button size="sm" variant="outline" onClick={cancelDescEdit} disabled={descSaving}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : dataset.description ? (
                <div className="mt-1">
                  <MarkdownViewer value={dataset.description} onClick={startDescEdit} />
                </div>
              ) : (
                <p
                  className="mt-1 text-sm cursor-pointer rounded-md px-2 py-1 -mx-2 hover:bg-muted transition-colors text-muted-foreground italic"
                  onClick={startDescEdit}
                  title="Click to edit"
                >
                  No description. Click to add.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Tabbed content */}
        <Tabs defaultValue="schema" className="flex-1">
          <TabsList>
            <TabsTrigger value="schema" className="gap-1.5">
              <Columns3 className="h-4 w-4" />
              Schema ({dataset.schema_fields.length})
            </TabsTrigger>
            <TabsTrigger value="tags" className="gap-1.5">
              <Tags className="h-4 w-4" />
              Tags ({dataset.tags.length})
            </TabsTrigger>
            <TabsTrigger value="owners" className="gap-1.5">
              <Users className="h-4 w-4" />
              Owners ({dataset.owners.length})
            </TabsTrigger>
            <TabsTrigger value="glossary" className="gap-1.5">
              <BookOpen className="h-4 w-4" />
              Glossary ({dataset.glossary_terms.length})
            </TabsTrigger>
            <TabsTrigger value="sample" className="gap-1.5">
              <Globe className="h-4 w-4" />
              Sample
            </TabsTrigger>
            <TabsTrigger value="avro" className="gap-1.5">
              <Code2 className="h-4 w-4" />
              Avro
            </TabsTrigger>
            <TabsTrigger value="spark" className="gap-1.5">
              <Flame className="h-4 w-4" />
              PySpark
            </TabsTrigger>
            <TabsTrigger value="nifi" className="gap-1.5">
              <Workflow className="h-4 w-4" />
              NiFi 2
            </TabsTrigger>
            <TabsTrigger value="kestra" className="gap-1.5">
              <Workflow className="h-4 w-4" />
              Kestra
            </TabsTrigger>
            <TabsTrigger value="airflow" className="gap-1.5">
              <Workflow className="h-4 w-4" />
              Airflow
            </TabsTrigger>
            <TabsTrigger value="history" className="gap-1.5">
              <History className="h-4 w-4" />
              History
            </TabsTrigger>
          </TabsList>

          {/* =============== Schema tab =============== */}
          <TabsContent value="schema" className="mt-4">
            <Card>
              <div className="flex justify-end px-4 pt-3">
                {schemaEditing ? (
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={cancelSchemaEdit}
                      disabled={schemaSaving}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={saveSchema}
                      disabled={schemaSaving}
                    >
                      {schemaSaving ? "Updating..." : "Update"}
                    </Button>
                  </div>
                ) : (
                  <Button size="sm" variant="outline" onClick={startSchemaEdit}>
                    <Pencil className="mr-1 h-3.5 w-3.5" />
                    Edit Schema
                  </Button>
                )}
              </div>
              <CardContent className="p-0">
                {schemaEditing ? (
                  /* ---------- AG Grid edit mode ---------- */
                  <div>
                    <SchemaEditGrid
                      fields={editFields}
                      onChange={setEditFields}
                      dataTypeOptions={dataTypeOptions.map(dt => dt.type_name)}
                    />

                    {/* Platform features section */}
                    {featuresMeta.length > 0 && (
                      <>
                        <Separator className="my-4" />
                        <div className="space-y-3">
                          <p className="text-xs font-medium text-muted-foreground">
                            Platform Features ({dataset.platform.name})
                          </p>
                          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {featuresMeta.map((feat) => {
                              const existing = dataset.properties?.find(
                                (p) => p.property_key === feat.feature_key
                              )
                              return (
                                <div key={feat.feature_key} className="grid gap-1">
                                  <label className="text-xs font-medium flex items-center gap-1">
                                    {feat.display_name}
                                    {feat.is_required === "true" && (
                                      <span className="text-destructive">*</span>
                                    )}
                                  </label>
                                  {feat.description && (
                                    <p className="text-xs text-muted-foreground truncate">
                                      {feat.description}
                                    </p>
                                  )}
                                  <Input
                                    placeholder={
                                      feat.value_type === "number"
                                        ? "0"
                                        : feat.value_type === "column_list"
                                          ? "col1, col2"
                                          : feat.value_type === "boolean"
                                            ? "true / false"
                                            : ""
                                    }
                                    defaultValue={existing?.property_value ?? ""}
                                    className="h-8 text-sm"
                                    disabled
                                  />
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                ) : dataset.schema_fields.length > 0 ? (
                  /* ---------- Read-only view ---------- */
                  <>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[50px]">#</TableHead>
                          <TableHead>Field</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Native Type</TableHead>
                          <TableHead className="w-[50px] text-center">PK</TableHead>
                          <TableHead className="w-[50px] text-center">Unique</TableHead>
                          <TableHead className="w-[50px] text-center">Index</TableHead>
                          <TableHead className="w-[50px] text-center">Nullable</TableHead>
                          <TableHead>Description</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {dataset.schema_fields.map((field, idx) => (
                          <TableRow key={field.id}>
                            <TableCell className="text-muted-foreground">
                              {idx + 1}
                            </TableCell>
                            <TableCell className="text-sm font-[family-name:var(--font-d2coding)]">
                              {field.field_path}
                            </TableCell>
                            <TableCell>
                              <Badge variant="secondary" className="font-mono text-xs">
                                {field.field_type}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm font-[family-name:var(--font-d2coding)] uppercase">
                              {field.native_type || "-"}
                            </TableCell>
                            <TableCell className="text-center">
                              {field.is_primary_key === "true" && (
                                <Check className="h-4 w-4 text-primary mx-auto" />
                              )}
                            </TableCell>
                            <TableCell className="text-center">
                              {field.is_unique === "true" && (
                                <Check className="h-4 w-4 text-primary mx-auto" />
                              )}
                            </TableCell>
                            <TableCell className="text-center">
                              {field.is_indexed === "true" && (
                                <Check className="h-4 w-4 text-muted-foreground mx-auto" />
                              )}
                            </TableCell>
                            <TableCell className="text-center">
                              {field.nullable === "true" && (
                                <Check className="h-4 w-4 text-muted-foreground mx-auto" />
                              )}
                            </TableCell>
                            <TableCell className="text-sm min-w-[200px] max-w-[500px]">
                              <span className="whitespace-pre-wrap break-words">
                                {field.description || "-"}
                              </span>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    {/* Platform features read-only */}
                    {dataset.properties && dataset.properties.length > 0 && (
                      <div className="p-4 border-t">
                        <p className="text-xs font-medium text-muted-foreground mb-2">
                          Platform Features
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {dataset.properties.map((p) => (
                            <Badge key={p.id} variant="outline" className="text-xs font-mono">
                              {p.property_key}: {p.property_value}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="flex items-center justify-center p-8">
                    <p className="text-muted-foreground">No schema fields defined.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* =============== Tags tab =============== */}
          <TabsContent value="tags" className="mt-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between py-3">
                <CardTitle className="text-base">Tags</CardTitle>
                <Popover open={tagPopoverOpen} onOpenChange={setTagPopoverOpen}>
                  <PopoverTrigger asChild>
                    <Button size="sm" variant="outline" disabled={availableTags.length === 0}>
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      Add Tag
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="p-0" align="end">
                    <Command>
                      <CommandInput placeholder="Search tags..." />
                      <CommandList>
                        <CommandEmpty>No tags found</CommandEmpty>
                        <CommandGroup>
                          {availableTags.map((tag) => (
                            <CommandItem
                              key={tag.id}
                              value={tag.name}
                              onSelect={() => handleAddTag(tag.id)}
                            >
                              <span
                                className="inline-block h-3 w-3 rounded-full mr-2 shrink-0"
                                style={{ backgroundColor: tag.color }}
                              />
                              {tag.name}
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </CardHeader>
              <CardContent className="pt-2">
                {dataset.tags.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {dataset.tags.map((tag) => (
                      <Badge
                        key={tag.id}
                        style={{ backgroundColor: tag.color, color: "#fff" }}
                        className="text-sm px-3 py-1 gap-1.5"
                      >
                        {tag.name}
                        <button
                          className="ml-1 hover:opacity-70 cursor-pointer"
                          onClick={() => handleRemoveTag(tag.id)}
                          aria-label={`Remove tag ${tag.name}`}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground">No tags attached</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* =============== Owners tab =============== */}
          <TabsContent value="owners" className="mt-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between py-3">
                <CardTitle className="text-base">Owners</CardTitle>
                <div className="flex items-center gap-2">
                  {/* Owner type selector */}
                  <Select value={ownerType} onValueChange={setOwnerType}>
                    <SelectTrigger size="sm" className="w-[180px] h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="TECHNICAL_OWNER">Technical Owner</SelectItem>
                      <SelectItem value="BUSINESS_OWNER">Business Owner</SelectItem>
                      <SelectItem value="DATA_STEWARD">Data Steward</SelectItem>
                    </SelectContent>
                  </Select>
                  {/* Add owner popover */}
                  <Popover
                    open={ownerPopoverOpen}
                    onOpenChange={(open) => {
                      setOwnerPopoverOpen(open)
                      if (!open) {
                        setOwnerSearchQuery("")
                        setOwnerSearchUsers([])
                      }
                    }}
                  >
                    <PopoverTrigger asChild>
                      <Button size="sm" variant="outline">
                        <Plus className="mr-1 h-3.5 w-3.5" />
                        Add Owner
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="p-0" align="end">
                      <Command shouldFilter={false}>
                        <CommandInput
                          placeholder="Search users..."
                          value={ownerSearchQuery}
                          onValueChange={setOwnerSearchQuery}
                        />
                        <CommandList>
                          {ownerSearchQuery.trim() === "" ? (
                            <div className="p-4 text-center text-sm text-muted-foreground">
                              Type to search users
                            </div>
                          ) : ownerSearching ? (
                            <div className="p-4 text-center text-sm text-muted-foreground">
                              Searching...
                            </div>
                          ) : availableUsers.length === 0 ? (
                            <CommandEmpty>No users found</CommandEmpty>
                          ) : (
                            <CommandGroup>
                              {availableUsers.map((user) => (
                                <CommandItem
                                  key={user.id}
                                  value={user.id}
                                  onSelect={() => handleAddOwner(user)}
                                >
                                  <div className="flex flex-col">
                                    <span className="font-medium">
                                      {user.firstName} {user.lastName}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                      {user.username} · {user.email}
                                    </span>
                                  </div>
                                </CommandItem>
                              ))}
                            </CommandGroup>
                          )}
                        </CommandList>
                      </Command>
                    </PopoverContent>
                  </Popover>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {dataset.owners.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Owner</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Added</TableHead>
                        <TableHead className="w-[60px]" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dataset.owners.map((owner) => (
                        <TableRow key={owner.id}>
                          <TableCell className="font-medium">
                            {owner.owner_name}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">
                              {owner.owner_type.replaceAll("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {new Date(owner.created_at).toLocaleDateString()}
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => handleRemoveOwner(owner.id)}
                              aria-label={`Remove owner ${owner.owner_name}`}
                            >
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="flex items-center justify-center p-8">
                    <p className="text-muted-foreground">No owners assigned</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* =============== Glossary tab =============== */}
          <TabsContent value="glossary" className="mt-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between py-3">
                <CardTitle className="text-base">Glossary Terms</CardTitle>
                <Popover open={glossaryPopoverOpen} onOpenChange={setGlossaryPopoverOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={availableGlossary.length === 0}
                    >
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      Add Term
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="p-0" align="end">
                    <Command>
                      <CommandInput placeholder="Search glossary..." />
                      <CommandList>
                        <CommandEmpty>No terms found</CommandEmpty>
                        <CommandGroup>
                          {availableGlossary.map((term) => (
                            <CommandItem
                              key={term.id}
                              value={term.name}
                              onSelect={() => handleAddGlossary(term.id)}
                            >
                              <div className="flex flex-col">
                                <span className="font-medium">{term.name}</span>
                                {term.source && (
                                  <span className="text-xs text-muted-foreground">
                                    {term.source}
                                  </span>
                                )}
                              </div>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </CardHeader>
              <CardContent className="p-0">
                {dataset.glossary_terms.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Term</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Source</TableHead>
                        <TableHead className="w-[60px]" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dataset.glossary_terms.map((term) => (
                        <TableRow key={term.id}>
                          <TableCell className="font-medium">
                            {term.name}
                          </TableCell>
                          <TableCell className="text-sm max-w-[300px] truncate">
                            {term.description || "-"}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {term.source || "-"}
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => handleRemoveGlossary(term.id)}
                              aria-label={`Remove term ${term.name}`}
                            >
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="flex items-center justify-center p-8">
                    <p className="text-muted-foreground">
                      No glossary terms attached
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* =============== Sample tab =============== */}
          <TabsContent value="sample" className="mt-4">
            <SampleDataTab datasetId={datasetId} isSynced={dataset.is_synced === "true"} />
          </TabsContent>

          {/* =============== Avro tab =============== */}
          <TabsContent value="avro" className="mt-4">
            <AvroSchemaCard dataset={dataset} />
          </TabsContent>

          {/* =============== Spark tab =============== */}
          <TabsContent value="spark" className="mt-4">
            <SparkCodeCard dataset={dataset} />
          </TabsContent>

          {/* =============== NiFi tab =============== */}
          <TabsContent value="nifi" className="mt-4">
            <NiFiFlowTab dataset={dataset} />
          </TabsContent>

          {/* =============== Kestra tab =============== */}
          <TabsContent value="kestra" className="mt-4">
            <KestraFlowTab dataset={dataset} />
          </TabsContent>

          {/* =============== Airflow tab =============== */}
          <TabsContent value="airflow" className="mt-4">
            <AirflowDagTab dataset={dataset} />
          </TabsContent>

          {/* =============== History tab =============== */}
          <TabsContent value="history" className="mt-4">
            <SchemaHistoryTab datasetId={datasetId} />
          </TabsContent>
        </Tabs>

        {/* Platform Specific */}
        {dataset.platform_properties && (
          <PlatformSpecificCard
            platformType={dataset.platform.type}
            properties={dataset.platform_properties}
          />
        )}
      </div>

    </>
  )
}

// ---------------------------------------------------------------------------
// Avro Schema Card with line numbers
// ---------------------------------------------------------------------------
function AvroSchemaCard({ dataset }: { dataset: DatasetDetail }) {
  const schema = useMemo(() => {
    if (dataset.schema_fields.length === 0) return ""
    const schemaName = dataset.name.split(".").pop() || dataset.name
    return generateAvroSchema(
      schemaName,
      `argus.catalog.${dataset.platform.platform_id}.${dataset.name.split(".").slice(0, -1).join(".")}`,
      dataset.schema_fields
    )
  }, [dataset.name, dataset.platform.platform_id, dataset.schema_fields])

  const lineCount = useMemo(() => schema.split("\n").length, [schema])

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between py-3">
        <CardTitle className="text-base">Avro Schema</CardTitle>
        {schema && (
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(schema)
                toast.success("Copied to clipboard.")
              } catch {
                toast.error("Failed to copy. Clipboard API requires HTTPS.")
              }
            }}
          >
            Copy
          </Button>
        )}
      </CardHeader>
      <CardContent className="p-0">
        {schema ? (
          <div className="border-t">
            <MonacoEditor
              height={Math.min(lineCount * 20 + 20, 600)}
              language="json"
              value={schema}
              theme="vs"
              options={{
                readOnly: true,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                fontSize: 13,
                fontFamily: "var(--font-d2coding), 'D2Coding', Consolas, 'Courier New', monospace",
                lineNumbers: "on",
                renderLineHighlight: "none",
                overviewRulerLanes: 0,
                hideCursorInOverviewRuler: true,
                scrollbar: { vertical: "auto", horizontal: "auto" },
                wordWrap: "off",
                domReadOnly: true,
                padding: { top: 8, bottom: 8 },
              }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center p-8">
            <p className="text-muted-foreground">
              Define schema fields first to generate Avro schema.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// PySpark Code Card with Monaco Editor
// ---------------------------------------------------------------------------
import dynamic from "next/dynamic"
const MonacoEditor = dynamic(() => import("@monaco-editor/react").then(m => m.default), { ssr: false })

function SparkCodeCard({ dataset }: { dataset: DatasetDetail }) {
  const code = useMemo(() => {
    if (dataset.schema_fields.length === 0) return ""
    return generatePySparkCode(dataset)
  }, [dataset])

  const lineCount = useMemo(() => code.split("\n").length, [code])

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between py-3">
        <div>
          <CardTitle className="text-base">PySpark Code</CardTitle>
          <CardDescription className="text-xs mt-1">
            JDBC read from {dataset.platform.type} and write to HDFS as Parquet.
            Date partitioning code is included as comments.
          </CardDescription>
        </div>
        {code && (
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(code)
                toast.success("Copied to clipboard.")
              } catch {
                toast.error("Failed to copy. Clipboard API requires HTTPS.")
              }
            }}
          >
            Copy
          </Button>
        )}
      </CardHeader>
      <CardContent className="p-0">
        {code ? (
          <div className="border-t">
            <MonacoEditor
              height={Math.min(lineCount * 20 + 20, 600)}
              language="python"
              value={code}
              theme="vs"
              options={{
                readOnly: true,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                fontSize: 13,
                fontFamily: "var(--font-d2coding), 'D2Coding', Consolas, 'Courier New', monospace",
                lineNumbers: "on",
                renderLineHighlight: "none",
                overviewRulerLanes: 0,
                hideCursorInOverviewRuler: true,
                scrollbar: { vertical: "auto", horizontal: "auto" },
                wordWrap: "off",
                domReadOnly: true,
                padding: { top: 8, bottom: 8 },
              }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center p-8">
            <p className="text-muted-foreground">
              Define schema fields first to generate PySpark code.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
