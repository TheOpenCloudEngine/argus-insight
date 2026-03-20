"use client"

import { useCallback, useEffect, useState } from "react"
import { Eye, EyeOff, Pencil, Plus, Server, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Switch } from "@workspace/ui/components/switch"
import { DashboardHeader } from "@/components/dashboard-header"
import type { Platform } from "@/features/datasets/data/schema"
import {
  PLATFORM_CONFIGS,
  getDefaultConfig,
  type PlatformFieldDef,
} from "@/features/platforms/platform-configs"

const BASE = "/api/v1/catalog"

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function fetchPlatforms(): Promise<Platform[]> {
  const res = await fetch(`${BASE}/platforms`)
  if (!res.ok) throw new Error(`Failed: ${res.status}`)
  return res.json()
}

async function createPlatform(payload: {
  name: string
  type: string
}): Promise<Platform> {
  const res = await fetch(`${BASE}/platforms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed: ${res.status}`)
  }
  return res.json()
}

async function deletePlatform(id: number): Promise<void> {
  const res = await fetch(`${BASE}/platforms/${id}`, { method: "DELETE" })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed: ${res.status}`)
  }
}

async function fetchPlatformConfig(id: number): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${BASE}/platforms/${id}/configuration`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`Failed: ${res.status}`)
  const data = await res.json()
  return data.config
}

async function savePlatformConfig(id: number, config: Record<string, unknown>): Promise<void> {
  const res = await fetch(`${BASE}/platforms/${id}/configuration`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  })
  if (!res.ok) throw new Error(`Failed: ${res.status}`)
}

async function fetchDatasetCount(id: number): Promise<number> {
  const res = await fetch(`${BASE}/platforms/${id}/dataset-count`)
  if (!res.ok) return 0
  const data = await res.json()
  return data.count
}

// ---------------------------------------------------------------------------
// Supported platform types for "Add Platform"
// ---------------------------------------------------------------------------

const PLATFORM_TYPES = [
  { name: "postgresql", display: "PostgreSQL" },
  { name: "mysql", display: "MySQL" },
  { name: "hive", display: "Apache Hive" },
  { name: "impala", display: "Apache Impala" },
  { name: "kafka", display: "Apache Kafka" },
  { name: "s3", display: "Amazon S3" },
  { name: "hdfs", display: "HDFS" },
  { name: "snowflake", display: "Snowflake" },
  { name: "bigquery", display: "Google BigQuery" },
  { name: "redshift", display: "Amazon Redshift" },
  { name: "elasticsearch", display: "Elasticsearch" },
  { name: "mongodb", display: "MongoDB" },
  { name: "trino", display: "Trino" },
  { name: "starrocks", display: "StarRocks" },
  { name: "greenplum", display: "Greenplum" },
  { name: "kudu", display: "Apache Kudu" },
  { name: "unity_catalog", display: "Unity Catalog" },
]

// ---------------------------------------------------------------------------
// Validation helper
// ---------------------------------------------------------------------------

function hasRequiredFields(
  fields: PlatformFieldDef[],
  values: Record<string, unknown>,
): boolean {
  const seen = new Set<string>()
  for (const field of fields) {
    if (seen.has(field.key)) continue
    seen.add(field.key)
    if (!field.required) continue

    // Skip hidden fields
    if (field.showWhen) {
      const allConditions = fields
        .filter((f) => f.key === field.key && f.showWhen)
        .map((f) => f.showWhen!)
      const visible = allConditions.some(
        (cond) => String(values[cond.field] ?? "") === cond.value
      )
      if (!visible) continue
    }

    const val = values[field.key]
    if (val === undefined || val === null || val === "") return false
  }
  return true
}

// ---------------------------------------------------------------------------
// Dynamic config form
// ---------------------------------------------------------------------------

function ConfigForm({
  fields,
  values,
  onChange,
}: {
  fields: PlatformFieldDef[]
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}) {
  // Track password visibility per field
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})

  // Deduplicate fields by key (e.g. kafka SASL duplicated for two protocols)
  const seen = new Set<string>()
  const uniqueFields = fields.filter((f) => {
    if (seen.has(f.key)) return false
    seen.add(f.key)
    return true
  })

  // Check visibility — merge showWhen from all duplicate definitions
  const isVisible = (field: PlatformFieldDef): boolean => {
    // Collect all showWhen conditions for this key
    const conditions = fields
      .filter((f) => f.key === field.key && f.showWhen)
      .map((f) => f.showWhen!)
    if (conditions.length === 0) return true
    // Visible if ANY condition matches
    return conditions.some((cond) => String(values[cond.field] ?? "") === cond.value)
  }

  return (
    <div className="grid gap-3">
      {uniqueFields.map((field) => {
        if (!isVisible(field)) return null

        if (field.type === "toggle") {
          return (
            <div key={field.key} className="flex items-center justify-between">
              <Label className="text-sm">{field.label}</Label>
              <Switch
                checked={Boolean(values[field.key] ?? field.defaultValue ?? false)}
                onCheckedChange={(v) => onChange(field.key, v)}
              />
            </div>
          )
        }

        if (field.type === "select") {
          return (
            <div key={field.key} className="grid gap-1.5">
              <Label className="text-sm">
                {field.label}
                {field.required && <span className="text-destructive ml-0.5">*</span>}
              </Label>
              <Select
                value={String(values[field.key] ?? field.defaultValue ?? "")}
                onValueChange={(v) => onChange(field.key, v)}
              >
                <SelectTrigger className="h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {field.options?.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value} className="text-sm">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )
        }

        const isPassword = field.type === "password"
        const showPw = showPasswords[field.key] ?? false

        return (
          <div key={field.key} className="grid gap-1.5">
            <Label className="text-sm">
              {field.label}
              {field.required && <span className="text-destructive ml-0.5">*</span>}
            </Label>
            <div className="relative">
              <Input
                type={isPassword && !showPw ? "password" : field.type === "number" ? "number" : "text"}
                placeholder={field.placeholder}
                value={String(values[field.key] ?? "")}
                onChange={(e) =>
                  onChange(
                    field.key,
                    field.type === "number" ? Number(e.target.value) || "" : e.target.value
                  )
                }
                className={`h-9 text-sm ${isPassword ? "pr-9" : ""}`}
              />
              {isPassword && (
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowPasswords((p) => ({ ...p, [field.key]: !showPw }))}
                  tabIndex={-1}
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PlatformsPage() {
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Add dialog
  const [addOpen, setAddOpen] = useState(false)
  const [addStep, setAddStep] = useState<"type" | "config">("type")
  const [selectedType, setSelectedType] = useState<string>("")
  const [addDisplayName, setAddDisplayName] = useState("")
  const [addConfig, setAddConfig] = useState<Record<string, unknown>>({})
  const [addSaving, setAddSaving] = useState(false)

  // Delete dialog
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deletePlatformTarget, setDeletePlatformTarget] = useState<Platform | null>(null)
  const [deleteConfirmInput, setDeleteConfirmInput] = useState("")
  const [deleting, setDeleting] = useState(false)

  // Edit dialog
  const [editOpen, setEditOpen] = useState(false)
  const [editPlatform, setEditPlatform] = useState<Platform | null>(null)
  const [editConfig, setEditConfig] = useState<Record<string, unknown>>({})
  const [editSaving, setEditSaving] = useState(false)
  const [editLoading, setEditLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      setPlatforms(await fetchPlatforms())
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // ---- Add Platform -------------------------------------------------------

  const openAddDialog = () => {
    setSelectedType("")
    setAddDisplayName("")
    setAddConfig({})
    setAddStep("type")
    setAddOpen(true)
  }

  const handleSelectType = (typeName: string) => {
    setSelectedType(typeName)
    const pt = PLATFORM_TYPES.find((t) => t.name === typeName)
    setAddDisplayName(pt?.display ?? typeName)
    setAddConfig(getDefaultConfig(typeName))
    setAddStep("config")
  }

  const handleAddSave = async () => {
    if (!selectedType || !addDisplayName.trim()) return
    setAddSaving(true)
    try {
      const created = await createPlatform({
        name: addDisplayName.trim(),
        type: selectedType,
      })
      await savePlatformConfig(created.id, addConfig)
      toast.success(`Platform "${addDisplayName}" has been created.`)
      setAddOpen(false)
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create platform")
    } finally {
      setAddSaving(false)
    }
  }

  // ---- Edit Platform ------------------------------------------------------

  const openEditDialog = async (platform: Platform) => {
    setEditPlatform(platform)
    setEditConfig({})
    setEditOpen(true)
    setEditLoading(true)
    try {
      const config = await fetchPlatformConfig(platform.id)
      if (config) {
        setEditConfig(config)
      } else {
        setEditConfig(getDefaultConfig(platform.type))
      }
    } catch {
      setEditConfig(getDefaultConfig(platform.type))
    } finally {
      setEditLoading(false)
    }
  }

  const handleEditSave = async () => {
    if (!editPlatform) return
    setEditSaving(true)
    try {
      await savePlatformConfig(editPlatform.id, editConfig)
      toast.success(`Configuration for "${editPlatform.name}" has been saved.`)
      setEditOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save configuration")
    } finally {
      setEditSaving(false)
    }
  }

  // ---- Delete Platform ----------------------------------------------------

  const openDeleteDialog = async (platform: Platform) => {
    try {
      const count = await fetchDatasetCount(platform.id)
      if (count > 0) {
        toast.error(
          `Cannot delete platform "${platform.name}": ${count} dataset(s) are using this platform.`
        )
        return
      }
    } catch {
      // proceed to dialog even if count check fails
    }
    setDeletePlatformTarget(platform)
    setDeleteConfirmInput("")
    setDeleteOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!deletePlatformTarget) return
    setDeleting(true)
    try {
      await deletePlatform(deletePlatformTarget.id)
      toast.success(`Platform "${deletePlatformTarget.name}" has been deleted.`)
      setDeleteOpen(false)
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete platform")
    } finally {
      setDeleting(false)
    }
  }

  const deleteExpectedInput = deletePlatformTarget
    ? `DELETE ${deletePlatformTarget.name}`
    : ""

  // ---- Render -------------------------------------------------------------

  const addFields = PLATFORM_CONFIGS[selectedType] ?? []
  const addConfigValid = addFields.length === 0 || hasRequiredFields(addFields, addConfig)
  const editFields = editPlatform ? (PLATFORM_CONFIGS[editPlatform.type] ?? []) : []
  const editConfigValid = editFields.length === 0 || hasRequiredFields(editFields, editConfig)

  return (
    <>
      <DashboardHeader title="Platforms" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Data platforms that host your datasets
          </p>
          <Button size="sm" onClick={openAddDialog}>
            <Plus className="mr-1 h-4 w-4" />
            Add Platform
          </Button>
        </div>

        <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {isLoading ? (
            <p className="text-muted-foreground col-span-full text-center py-8">
              Loading platforms...
            </p>
          ) : platforms.length === 0 ? (
            <p className="text-muted-foreground col-span-full text-center py-8">
              No platforms configured.
            </p>
          ) : (
            platforms.map((p) => (
              <Card key={p.id} className="transition-colors hover:bg-muted">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <Server className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <CardTitle className="text-sm truncate">
                        {p.name}
                      </CardTitle>
                    </div>
                    <div className="flex items-center">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => openEditDialog(p)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive"
                        onClick={() => openDeleteDialog(p)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-xs text-muted-foreground font-mono">
                    {p.type}
                  </p>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* ---- Add Platform Dialog ---- */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {addStep === "type" ? "Select Platform Type" : `Add ${addDisplayName}`}
            </DialogTitle>
            {addStep === "type" && (
              <DialogDescription>
                Choose the type of data platform to add.
              </DialogDescription>
            )}
          </DialogHeader>

          {addStep === "type" ? (
            <div className="grid grid-cols-2 gap-2 py-2">
              {PLATFORM_TYPES.map((pt) => (
                <Button
                  key={pt.name}
                  variant="outline"
                  className="justify-start h-auto py-2.5 px-3"
                  onClick={() => handleSelectType(pt.name)}
                >
                  <Server className="h-4 w-4 mr-2 shrink-0 text-muted-foreground" />
                  <div className="text-left">
                    <div className="text-sm font-medium">{pt.display}</div>
                    <div className="text-xs text-muted-foreground font-mono">{pt.name}</div>
                  </div>
                </Button>
              ))}
            </div>
          ) : (
            <div className="grid gap-4 py-2">
              <div className="grid gap-1.5">
                <Label className="text-sm">
                  Display Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  value={addDisplayName}
                  onChange={(e) => setAddDisplayName(e.target.value)}
                  placeholder="e.g. Production PostgreSQL"
                  className="h-9 text-sm"
                />
              </div>

              {addFields.length > 0 && (
                <>
                  <div className="border-t pt-3">
                    <p className="text-sm font-medium mb-3">Connection Settings</p>
                    <ConfigForm
                      fields={addFields}
                      values={addConfig}
                      onChange={(k, v) => setAddConfig((prev) => ({ ...prev, [k]: v }))}
                    />
                  </div>
                </>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setAddStep("type")} disabled={addSaving}>
                  Back
                </Button>
                <Button
                  onClick={handleAddSave}
                  disabled={addSaving || !addDisplayName.trim() || !addConfigValid}
                >
                  {addSaving ? "Creating..." : "Create"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ---- Edit Platform Dialog ---- */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editPlatform?.name} — Connection Settings
            </DialogTitle>
            <DialogDescription>
              Configure the connection to this {editPlatform?.type} instance.
            </DialogDescription>
          </DialogHeader>

          {editLoading ? (
            <p className="text-sm text-muted-foreground py-8 text-center">Loading...</p>
          ) : (
            <div className="grid gap-4 py-2">
              {editPlatform && PLATFORM_CONFIGS[editPlatform.type] ? (
                <ConfigForm
                  fields={PLATFORM_CONFIGS[editPlatform.type]!}
                  values={editConfig}
                  onChange={(k, v) => setEditConfig((prev) => ({ ...prev, [k]: v }))}
                />
              ) : (
                <p className="text-sm text-muted-foreground">
                  No configuration template available for this platform type.
                </p>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setEditOpen(false)} disabled={editSaving}>
                  Cancel
                </Button>
                <Button onClick={handleEditSave} disabled={editSaving || !editConfigValid}>
                  {editSaving ? "Saving..." : "Save"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ---- Delete Confirmation Dialog ---- */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Platform</DialogTitle>
            <DialogDescription>
              This action cannot be undone. To confirm, type{" "}
              <span className="font-mono font-semibold text-foreground">
                {deleteExpectedInput}
              </span>{" "}
              below.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <Input
              placeholder={deleteExpectedInput}
              value={deleteConfirmInput}
              onChange={(e) => setDeleteConfirmInput(e.target.value)}
              className="font-mono text-sm"
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setDeleteOpen(false)}
                disabled={deleting}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteConfirm}
                disabled={deleting || deleteConfirmInput !== deleteExpectedInput}
              >
                {deleting ? "Deleting..." : "Delete"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
