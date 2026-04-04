"use client"

import { useState } from "react"
import { Loader2, Upload } from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Separator } from "@workspace/ui/components/separator"
import { Textarea } from "@workspace/ui/components/textarea"

import { authFetch } from "@/features/auth/auth-fetch"
import { FilePickerDialog } from "@/features/ml-studio/components/file-picker-dialog"
import { CsvPreviewDialog } from "@/features/ml-studio/components/csv-preview-dialog"
import { ColumnsEditor, type ColumnDef } from "./columns-editor"

// ── CSV / TSV Config ──────────────────────────────────────

export function SourceCsvConfig({
  config,
  onChange,
  onBatchChange,
}: {
  config: Record<string, any>
  onChange: (key: string, value: any) => void
  onBatchChange?: (updates: Record<string, any>) => void
}) {
  const batchUpdate = (updates: Record<string, any>) => {
    if (onBatchChange) onBatchChange(updates)
    else Object.entries(updates).forEach(([k, v]) => onChange(k, v))
  }

  const [filePickerOpen, setFilePickerOpen] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [pendingBucket, setPendingBucket] = useState("")
  const [pendingPath, setPendingPath] = useState("")
  const [loading, setLoading] = useState(false)
  const columns: ColumnDef[] = config.columns || []

  // Step B: After preview confirm, call server API for type inference
  // `extraFields` ensures all confirmed values are included in the final update
  const loadColumnsFromServer = async (bucket: string, path: string, extraFields?: Record<string, any>) => {
    const wsId = sessionStorage.getItem("argus_last_workspace_id")
    if (!wsId || !bucket || !path) return
    setLoading(true)
    try {
      const res = await authFetch("/api/v1/ml-studio/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: Number(wsId),
          source_type: "minio",
          bucket,
          path,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const cols: ColumnDef[] = (data.columns || []).map((c: any) => ({
          name: c.name,
          dtype: c.dtype,
          action: "feature",
        }))
        // Include extraFields so we don't lose the confirmed settings
        batchUpdate({ ...extraFields, columns: cols, _row_count: data.row_count || 0 })
      }
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-3">
      {/* File selector */}
      <div className="space-y-1">
        <Label className="text-sm">File</Label>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="text-sm" onClick={() => setFilePickerOpen(true)}>
            <Upload className="mr-1.5 h-3.5 w-3.5" /> Select File
          </Button>
          {config.path ? (
            <span className="text-sm truncate">
              <Badge variant="secondary" className="text-[10px] font-mono mr-1">{config.bucket}</Badge>
              {config.path.split("/").pop()}
              {loading && <Loader2 className="ml-1 inline h-3 w-3 animate-spin" />}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground italic">No file selected</span>
          )}
        </div>
      </div>

      {/* Step 1: File Picker → sets pending file → opens Preview */}
      <FilePickerDialog
        open={filePickerOpen}
        onOpenChange={setFilePickerOpen}
        fileFilter={[".csv", ".tsv"]}
        onSelect={(b, p) => {
          setPendingBucket(b)
          setPendingPath(p)
          setPreviewOpen(true)
        }}
      />

      {/* Step 2: Preview Dialog → user confirms data looks correct */}
      <CsvPreviewDialog
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        bucket={pendingBucket}
        path={pendingPath}
        onConfirm={(opts) => {
          // Load columns and include all confirmed settings in one batch
          loadColumnsFromServer(pendingBucket, pendingPath, {
            bucket: pendingBucket,
            path: pendingPath,
            delimiter: opts.delimiter,
            encoding: opts.encoding,
            has_header: opts.hasHeader,
          })
        }}
      />

      {/* Change file button (when already selected) */}
      {config.path && columns.length > 0 && (
        <Button variant="ghost" size="sm" className="text-sm text-muted-foreground" onClick={() => setFilePickerOpen(true)}>
          Change File
        </Button>
      )}

      {/* Columns editor */}
      {columns.length > 0 && (
        <>
          <Separator />
          <ColumnsEditor
            columns={columns}
            onChange={(cols) => onChange("columns", cols)}
            typeEditable={true}
            rowCount={config._row_count}
          />
        </>
      )}
    </div>
  )
}

// ── Parquet Config ────────────────────────────────────────

export function SourceParquetConfig({
  config,
  onChange,
  onBatchChange,
}: {
  config: Record<string, any>
  onChange: (key: string, value: any) => void
  onBatchChange?: (updates: Record<string, any>) => void
}) {
  const batchUpdate = (updates: Record<string, any>) => {
    if (onBatchChange) onBatchChange(updates)
    else Object.entries(updates).forEach(([k, v]) => onChange(k, v))
  }

  const [filePickerOpen, setFilePickerOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const columns: ColumnDef[] = config.columns || []

  const loadColumns = async (bucket: string, path: string, extraFields?: Record<string, any>) => {
    const wsId = sessionStorage.getItem("argus_last_workspace_id")
    if (!wsId || !bucket || !path) return
    setLoading(true)
    try {
      const res = await authFetch("/api/v1/ml-studio/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: Number(wsId),
          source_type: "minio",
          bucket,
          path,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const cols: ColumnDef[] = (data.columns || []).map((c: any) => ({
          name: c.name,
          dtype: c.dtype,
          action: "feature",
        }))
        batchUpdate({ ...extraFields, columns: cols, _row_count: data.row_count || 0 })
      }
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-sm">File</Label>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="text-sm" onClick={() => setFilePickerOpen(true)}>
            <Upload className="mr-1.5 h-3.5 w-3.5" /> Select File
          </Button>
          {config.path ? (
            <span className="text-sm truncate">
              <Badge variant="secondary" className="text-[10px] font-mono mr-1">{config.bucket}</Badge>
              {config.path.split("/").pop()}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground italic">No file selected</span>
          )}
        </div>
      </div>

      <FilePickerDialog
        open={filePickerOpen}
        onOpenChange={setFilePickerOpen}
        fileFilter={[".parquet"]}
        onSelect={(b, p) => {
          loadColumns(b, p, { bucket: b, path: p })
        }}
      />

      {config.path && columns.length === 0 && (
        <Button variant="outline" size="sm" className="w-full text-sm" onClick={() => loadColumns(config.bucket, config.path)} disabled={loading}>
          {loading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
          Load Columns from Metadata
        </Button>
      )}

      {columns.length > 0 && (
        <>
          <Separator />
          <ColumnsEditor
            columns={columns}
            onChange={(cols) => onChange("columns", cols)}
            typeEditable={false}
            rowCount={config._row_count}
          />
        </>
      )}
    </div>
  )
}

// ── Database Query Config ─────────────────────────────────

export function SourceDatabaseConfig({
  config,
  onChange,
}: {
  config: Record<string, any>
  onChange: (key: string, value: any) => void
}) {
  const [loading, setLoading] = useState(false)
  const columns: ColumnDef[] = config.columns || []
  const mode = config.mode || "sql"

  // TODO: In future, load DB services from workspace and schemas/tables via API
  // For now, provide manual input with helpful labels

  return (
    <div className="space-y-3">
      {/* DB Service */}
      <div className="space-y-1">
        <Label className="text-sm">Database Type</Label>
        <Select value={config.db_type || "postgresql"} onValueChange={(v) => onChange("db_type", v)}>
          <SelectTrigger className="h-7 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="postgresql" className="text-sm">PostgreSQL</SelectItem>
            <SelectItem value="mariadb" className="text-sm">MariaDB</SelectItem>
            <SelectItem value="trino" className="text-sm">Trino</SelectItem>
            <SelectItem value="starrocks" className="text-sm">StarRocks</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label className="text-sm">Connection (internal hostname)</Label>
        <Input
          value={config.connection || ""}
          onChange={(e) => onChange("connection", e.target.value)}
          placeholder="argus-postgresql-mlops7:5432"
          className="h-7 text-sm font-mono"
        />
        <p className="text-[11px] text-muted-foreground">From workspace deployed services</p>
      </div>

      {/* Mode */}
      <div className="space-y-1">
        <Label className="text-sm">Mode</Label>
        <Select value={mode} onValueChange={(v) => onChange("mode", v)}>
          <SelectTrigger className="h-7 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="table" className="text-sm">Select Table</SelectItem>
            <SelectItem value="sql" className="text-sm">Custom SQL</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {mode === "table" && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-sm">Schema / Database</Label>
              <Input
                value={config.schema || ""}
                onChange={(e) => onChange("schema", e.target.value)}
                placeholder="public"
                className="h-7 text-sm font-mono"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-sm">Table</Label>
              <Input
                value={config.table || ""}
                onChange={(e) => onChange("table", e.target.value)}
                placeholder="customers"
                className="h-7 text-sm font-mono"
              />
            </div>
          </div>
        </>
      )}

      {mode === "sql" && (
        <div className="space-y-1">
          <Label className="text-sm">SQL Query</Label>
          <Textarea
            value={config.query || ""}
            onChange={(e) => onChange("query", e.target.value)}
            placeholder={"SELECT *\nFROM customers\nWHERE active = true"}
            className="text-sm font-mono min-h-[80px]"
            rows={4}
          />
          {config.query && !/^\s*SELECT/i.test(config.query) && (
            <p className="text-sm text-red-500">⚠ Query must start with SELECT</p>
          )}
        </div>
      )}

      {/* Credentials */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-sm">Username</Label>
          <Input
            value={config.username || ""}
            onChange={(e) => onChange("username", e.target.value)}
            placeholder="postgres"
            className="h-7 text-sm"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-sm">Password</Label>
          <Input
            type="password"
            value={config.password || ""}
            onChange={(e) => onChange("password", e.target.value)}
            className="h-7 text-sm"
          />
        </div>
      </div>

      {/* Columns */}
      {columns.length > 0 && (
        <>
          <Separator />
          <ColumnsEditor
            columns={columns}
            onChange={(cols) => onChange("columns", cols)}
            typeEditable={false}
            rowCount={config._row_count}
          />
        </>
      )}
    </div>
  )
}
