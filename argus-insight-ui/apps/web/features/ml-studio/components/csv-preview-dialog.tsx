"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Papa from "papaparse"
import { Loader2, RefreshCw } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Checkbox } from "@workspace/ui/components/checkbox"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import { authFetch } from "@/features/auth/auth-fetch"

interface CsvPreviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  bucket: string
  path: string
  onConfirm: (opts: { delimiter: string; encoding: string; hasHeader: boolean; rowCount: number; columnCount: number }) => void
}

const MAX_PREVIEW_ROWS = 100

export function CsvPreviewDialog({
  open,
  onOpenChange,
  bucket,
  path,
  onConfirm,
}: CsvPreviewDialogProps) {
  const [delimiter, setDelimiter] = useState("auto")
  const [encoding, setEncoding] = useState("UTF-8")
  const [hasHeader, setHasHeader] = useState(true)
  const [rows, setRows] = useState<string[][]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  // Resolve effective delimiter
  const effectiveDelimiter = useMemo(() => {
    if (delimiter !== "auto") return delimiter
    if (path.endsWith(".tsv")) return "\t"
    return ","
  }, [delimiter, path])

  // Fetch and parse file via presigned URL
  const fetchAndParse = useCallback(async () => {
    if (!bucket || !path || !open) return
    setLoading(true)
    setError("")
    setRows([])

    try {
      // Get presigned URL
      const urlRes = await authFetch(
        `/api/v1/objectfilemgr/objects/download-url?bucket=${encodeURIComponent(bucket)}&key=${encodeURIComponent(path)}`,
      )
      if (!urlRes.ok) throw new Error("Failed to get download URL")
      const { url } = await urlRes.json()

      // Fetch raw file
      const fileRes = await fetch(url)
      if (!fileRes.ok) throw new Error(`Failed to fetch file: ${fileRes.status}`)
      const buffer = await fileRes.arrayBuffer()
      const decoded = new TextDecoder(encoding).decode(buffer)

      // Parse with PapaParse
      const result = Papa.parse(decoded, {
        delimiter: effectiveDelimiter,
        header: false,
        skipEmptyLines: true,
        preview: MAX_PREVIEW_ROWS + 1, // +1 for header
      })

      setRows(result.data as string[][])
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load file")
    } finally {
      setLoading(false)
    }
  }, [bucket, path, open, encoding, effectiveDelimiter])

  // Load on open
  useEffect(() => {
    if (open && bucket && path) fetchAndParse()
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Split header and data
  const display = useMemo(() => {
    if (rows.length === 0) return { header: null, data: [], totalCols: 0 }
    const totalCols = Math.max(...rows.map((r) => r.length))
    if (hasHeader) {
      return { header: rows[0], data: rows.slice(1), totalCols }
    }
    const autoHeader = Array.from({ length: totalCols }, (_, i) => `Col_${i + 1}`)
    return { header: autoHeader, data: rows, totalCols }
  }, [rows, hasHeader])

  const handleConfirm = () => {
    onConfirm({
      delimiter: effectiveDelimiter,
      encoding,
      hasHeader,
      rowCount: display.data.length,
      columnCount: display.totalCols,
    })
    onOpenChange(false)
  }

  const fileName = path.split("/").pop() || path

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm">
            Data Preview: {fileName}
          </DialogTitle>
        </DialogHeader>

        {/* Parse options */}
        <div className="flex items-center gap-3 flex-wrap text-sm pb-1">
          <div className="flex items-center gap-1.5">
            <Label className="text-sm shrink-0">Delimiter:</Label>
            <Select value={delimiter} onValueChange={setDelimiter}>
              <SelectTrigger className="h-7 w-[120px] text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="auto" className="text-sm">Auto-detect</SelectItem>
                <SelectItem value="," className="text-sm">Comma (,)</SelectItem>
                <SelectItem value="&#9;" className="text-sm">Tab (\t)</SelectItem>
                <SelectItem value=";" className="text-sm">Semicolon (;)</SelectItem>
                <SelectItem value="|" className="text-sm">Pipe (|)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-1.5">
            <Label className="text-sm shrink-0">Encoding:</Label>
            <Select value={encoding} onValueChange={setEncoding}>
              <SelectTrigger className="h-7 w-[100px] text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="UTF-8" className="text-sm">UTF-8</SelectItem>
                <SelectItem value="EUC-KR" className="text-sm">EUC-KR</SelectItem>
                <SelectItem value="ISO-8859-1" className="text-sm">Latin-1</SelectItem>
                <SelectItem value="Shift_JIS" className="text-sm">Shift-JIS</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <label className="flex items-center gap-1.5">
            <Checkbox checked={hasHeader} onCheckedChange={(v) => setHasHeader(!!v)} />
            <span className="text-sm">First row is header</span>
          </label>

          <Button variant="outline" size="sm" className="h-7 text-sm" onClick={fetchAndParse} disabled={loading}>
            <RefreshCw className={`mr-1 h-3 w-3 ${loading ? "animate-spin" : ""}`} /> Reload
          </Button>

          {!loading && rows.length > 0 && (
            <span className="text-sm text-muted-foreground ml-auto">
              {display.data.length} rows · {display.totalCols} columns
            </span>
          )}
        </div>

        {/* Data table */}
        <div className="flex-1 min-h-0 overflow-auto rounded border">
          {loading ? (
            <div className="flex items-center justify-center h-[300px]">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-[200px] text-sm text-red-500">{error}</div>
          ) : rows.length === 0 ? (
            <div className="flex items-center justify-center h-[200px] text-sm text-muted-foreground">No data</div>
          ) : (
            <table className="w-full text-sm border-collapse" style={{ fontFamily: "'Roboto Condensed', Roboto, sans-serif" }}>
              {display.header && (
                <thead className="bg-muted/60 sticky top-0 z-10">
                  <tr>
                    <th className="px-2 py-1 text-right text-muted-foreground border-r w-10 font-medium text-sm">#</th>
                    {display.header.map((cell, i) => (
                      <th key={i} className="px-2 py-1 text-left font-semibold border-r last:border-r-0 whitespace-nowrap text-sm">{cell}</th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody className="divide-y">
                {display.data.map((row, ri) => (
                  <tr key={ri} className="hover:bg-muted/30">
                    <td className="px-2 py-0.5 text-right text-muted-foreground border-r tabular-nums text-sm">{ri + 1}</td>
                    {Array.from({ length: display.totalCols }, (_, ci) => (
                      <td
                        key={ci}
                        className="px-2 py-0.5 border-r last:border-r-0 whitespace-nowrap max-w-[200px] truncate text-sm"
                        title={row[ci] ?? ""}
                      >
                        {row[ci] ?? ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" size="sm" className="text-sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button size="sm" className="text-sm" onClick={handleConfirm} disabled={loading || rows.length === 0}>
            Confirm & Load Columns
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
