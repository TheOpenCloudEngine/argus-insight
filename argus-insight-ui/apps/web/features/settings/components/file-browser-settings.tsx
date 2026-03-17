"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Save } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Separator } from "@workspace/ui/components/separator"
import { Badge } from "@workspace/ui/components/badge"

import type { FilebrowserConfig, PreviewCategoryConfig } from "@/features/object-storage/api"
import {
  fetchFilebrowserConfig,
  updateBrowserSettings,
  updatePreviewCategory,
} from "@/features/object-storage/api"

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

const SIZE_UNITS = ["B", "KB", "MB", "GB"] as const
type SizeUnit = (typeof SIZE_UNITS)[number]

const UNIT_MULTIPLIERS: Record<SizeUnit, number> = {
  B: 1,
  KB: 1024,
  MB: 1024 * 1024,
  GB: 1024 * 1024 * 1024,
}

/** Split raw bytes into a numeric value + best-fit unit. */
function bytesToSizeParts(bytes: number): { value: number; unit: SizeUnit } {
  if (bytes === 0) return { value: 0, unit: "B" }
  const k = 1024
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), SIZE_UNITS.length - 1)
  const unit = SIZE_UNITS[i]!
  const value = bytes / Math.pow(k, i)
  return { value: Number.isInteger(value) ? value : parseFloat(value.toFixed(1)), unit }
}

/** Combine numeric value + unit back to raw bytes. */
function sizePartsToBytes(value: number, unit: SizeUnit): number {
  return Math.round(value * UNIT_MULTIPLIERS[unit])
}

// --------------------------------------------------------------------------- //
// Browser Settings Section
// --------------------------------------------------------------------------- //

type BrowserSettingsField = {
  key: string
  label: string
  description: string
}

const BROWSER_FIELDS: BrowserSettingsField[] = [
  {
    key: "sort_disable_threshold",
    label: "Sort Disable Threshold",
    description: "Disable sorting when directory has this many or more entries",
  },
  {
    key: "max_keys_per_page",
    label: "Max Keys Per Page",
    description: "Maximum number of objects returned per list request",
  },
  {
    key: "max_delete_keys",
    label: "Max Delete Keys",
    description: "Maximum number of objects per delete request",
  },
]

function BrowserSettingsSection({
  values,
  onChange,
  onSave,
  saving,
}: {
  values: Record<string, number>
  onChange: (key: string, value: number) => void
  onSave: () => void
  saving: boolean
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>File Browser Settings</CardTitle>
            <CardDescription>
              General settings for the file browser behavior
            </CardDescription>
          </div>
          <Button size="sm" onClick={onSave} disabled={saving} className="bg-blue-600 text-white hover:bg-blue-700">
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
            ) : (
              <Save className="h-4 w-4 mr-1.5" />
            )}
            Save
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {BROWSER_FIELDS.map((field) => (
            <div key={field.key} className="space-y-2">
              <Label htmlFor={`browser-${field.key}`}>{field.label}</Label>
              <Input
                id={`browser-${field.key}`}
                type="number"
                min={1}
                value={values[field.key] ?? ""}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10)
                  if (!isNaN(v)) onChange(field.key, v)
                }}
              />
              <p className="text-xs text-muted-foreground">{field.description}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// --------------------------------------------------------------------------- //
// Preview Category Row
// --------------------------------------------------------------------------- //

function PreviewCategoryRow({
  category,
  onSave,
  saving,
}: {
  category: PreviewCategoryConfig
  onSave: (category: string, maxFileSize: number, maxPreviewRows: number | null) => void
  saving: string | null
}) {
  const initial = bytesToSizeParts(category.max_file_size)
  const [sizeValue, setSizeValue] = useState(initial.value)
  const [sizeUnit, setSizeUnit] = useState<SizeUnit>(initial.unit)
  const [maxPreviewRows, setMaxPreviewRows] = useState(
    category.max_preview_rows?.toString() ?? "",
  )
  const isSaving = saving === category.category

  // Sync state when category prop changes (after parent reload)
  useEffect(() => {
    const parts = bytesToSizeParts(category.max_file_size)
    setSizeValue(parts.value)
    setSizeUnit(parts.unit)
    setMaxPreviewRows(category.max_preview_rows?.toString() ?? "")
  }, [category.max_file_size, category.max_preview_rows])

  function handleSave() {
    const bytes = sizePartsToBytes(sizeValue, sizeUnit)
    const rows = maxPreviewRows ? parseInt(maxPreviewRows, 10) : null
    onSave(category.category, bytes, rows)
  }

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-medium">{category.label}</span>
          <Badge variant="secondary" className="text-xs font-mono">
            {category.category}
          </Badge>
        </div>
        <Button size="sm" onClick={handleSave} disabled={isSaving} className="bg-blue-600 text-white hover:bg-blue-700">
          {isSaving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
          ) : (
            <Save className="h-3.5 w-3.5 mr-1" />
          )}
          Save
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`size-${category.category}`} className="text-xs">
            Max File Size
          </Label>
          <div className="flex gap-1.5">
            <Input
              id={`size-${category.category}`}
              type="number"
              min={0}
              step="any"
              value={sizeValue}
              onChange={(e) => {
                const v = parseFloat(e.target.value)
                if (!isNaN(v)) setSizeValue(v)
              }}
              className="h-8 text-sm flex-1"
            />
            <select
              value={sizeUnit}
              onChange={(e) => setSizeUnit(e.target.value as SizeUnit)}
              className="h-8 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            >
              {SIZE_UNITS.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={`rows-${category.category}`} className="text-xs">
            Max Preview Rows
          </Label>
          <Input
            id={`rows-${category.category}`}
            type="number"
            min={0}
            value={maxPreviewRows}
            onChange={(e) => setMaxPreviewRows(e.target.value)}
            placeholder="N/A"
            disabled={category.max_preview_rows === null && !maxPreviewRows}
            className="h-8 text-sm"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        {category.extensions.map((ext) => (
          <Badge key={ext} variant="outline" className="text-xs font-mono">
            .{ext}
          </Badge>
        ))}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Preview Settings Section
// --------------------------------------------------------------------------- //

function PreviewSettingsSection({
  categories,
  onSave,
  savingCategory,
}: {
  categories: PreviewCategoryConfig[]
  onSave: (category: string, maxFileSize: number, maxPreviewRows: number | null) => void
  savingCategory: string | null
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Preview Settings</CardTitle>
        <CardDescription>
          Configure file size limits and preview rows per file category
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 lg:grid-cols-2">
          {categories.map((cat) => (
            <PreviewCategoryRow
              key={cat.category}
              category={cat}
              onSave={onSave}
              saving={savingCategory}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// --------------------------------------------------------------------------- //
// Main Component
// --------------------------------------------------------------------------- //

export function FileBrowserSettings() {
  const [config, setConfig] = useState<FilebrowserConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Browser settings local state
  const [browserValues, setBrowserValues] = useState<Record<string, number>>({})
  const [savingBrowser, setSavingBrowser] = useState(false)
  const [savingCategory, setSavingCategory] = useState<string | null>(null)

  // Status messages
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchFilebrowserConfig()
      setConfig(data)
      setBrowserValues({ ...data.browser })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  function showStatus(type: "success" | "error", text: string) {
    setStatusMessage({ type, text })
    setTimeout(() => setStatusMessage(null), 3000)
  }

  async function handleSaveBrowser() {
    setSavingBrowser(true)
    try {
      await updateBrowserSettings(browserValues)
      showStatus("success", "Browser settings saved successfully")
      await loadConfig()
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSavingBrowser(false)
    }
  }

  async function handleSavePreview(
    category: string,
    maxFileSize: number,
    maxPreviewRows: number | null,
  ) {
    setSavingCategory(category)
    try {
      await updatePreviewCategory(category, maxFileSize, maxPreviewRows)
      showStatus("success", `Preview settings for "${category}" saved successfully`)
      await loadConfig()
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSavingCategory(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Loading configuration...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" onClick={loadConfig}>
          Retry
        </Button>
      </div>
    )
  }

  if (!config) return null

  return (
    <div className="space-y-6">
      {/* Status message */}
      {statusMessage && (
        <div
          className={`rounded-md px-4 py-2 text-sm ${
            statusMessage.type === "success"
              ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
              : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
          }`}
        >
          {statusMessage.text}
        </div>
      )}

      {/* Browser Settings */}
      <BrowserSettingsSection
        values={browserValues}
        onChange={(key, value) =>
          setBrowserValues((prev) => ({ ...prev, [key]: value }))
        }
        onSave={handleSaveBrowser}
        saving={savingBrowser}
      />

      <Separator />

      {/* Preview Settings */}
      <PreviewSettingsSection
        categories={config.preview}
        onSave={handleSavePreview}
        savingCategory={savingCategory}
      />
    </div>
  )
}
