"use client"

import { useState } from "react"
import { FolderOpen } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { FilePickerDialog } from "./file-picker-dialog"

// ── Output CSV Export ────────────────────────────────────────

export function OutputCsvConfig({
  config,
  onChange,
  onBatchChange,
}: {
  config: Record<string, any>
  onChange: (key: string, value: any) => void
  onBatchChange: (updates: Record<string, any>) => void
}) {
  const [pickerOpen, setPickerOpen] = useState(false)

  const handleSelect = (bucket: string, selectedPath: string) => {
    // Determine if a file or directory was selected
    const isDirectory = selectedPath === "" || selectedPath.endsWith("/")

    if (isDirectory) {
      // Directory selected → generate UUID filename
      const uuid8 = Math.random().toString(36).slice(2, 10)
      const filename = `export_${uuid8}.csv`
      const dirPath = selectedPath.replace(/\/$/, "") // strip trailing slash
      onBatchChange({ bucket, path: dirPath, filename })
    } else {
      // File selected → split into directory + filename
      const lastSlash = selectedPath.lastIndexOf("/")
      const dirPath = lastSlash >= 0 ? selectedPath.slice(0, lastSlash) : ""
      const filename = lastSlash >= 0 ? selectedPath.slice(lastSlash + 1) : selectedPath
      onBatchChange({ bucket, path: dirPath, filename })
    }
  }

  const fullPath = [config.bucket, config.path, config.filename]
    .filter(Boolean)
    .join("/")
    .replace(/\/+/g, "/")

  return (
    <div className="space-y-3">
      <Button
        variant="outline"
        size="sm"
        className="w-full text-sm"
        onClick={() => setPickerOpen(true)}
      >
        <FolderOpen className="mr-1.5 h-3.5 w-3.5" /> Browse Storage...
      </Button>

      <div className="space-y-1">
        <Label className="text-sm">Bucket</Label>
        <Input
          value={config.bucket ?? ""}
          onChange={(e) => onChange("bucket", e.target.value)}
          placeholder="my-bucket"
          className="h-7 text-sm font-mono bg-muted/30"
          readOnly
        />
      </div>

      <div className="space-y-1">
        <Label className="text-sm">Path</Label>
        <Input
          value={config.path ?? ""}
          onChange={(e) => onChange("path", e.target.value)}
          placeholder="data/output"
          className="h-7 text-sm font-mono bg-muted/30"
          readOnly
        />
      </div>

      <div className="space-y-1">
        <Label className="text-sm">Filename</Label>
        <Input
          value={config.filename ?? ""}
          onChange={(e) => onChange("filename", e.target.value)}
          placeholder="predictions.csv"
          className="h-7 text-sm font-mono"
        />
        <p className="text-[11px] text-muted-foreground">Editable — auto-generated when selecting a folder</p>
      </div>

      {fullPath && (
        <div className="rounded bg-muted/30 px-2 py-1.5">
          <p className="text-[11px] text-muted-foreground mb-0.5">Output path:</p>
          <p className="text-sm font-mono truncate">s3://{fullPath}</p>
        </div>
      )}

      <FilePickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        onSelect={handleSelect}
        fileFilter={[".csv"]}
        allowDirectory
      />
    </div>
  )
}
