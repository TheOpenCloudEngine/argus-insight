"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Papa from "papaparse"
import { Loader2, RefreshCw } from "lucide-react"

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

const ENCODINGS = [
  "UTF-8",
  "EUC-KR",
  "ISO-8859-1",
  "Shift_JIS",
  "Windows-1252",
  "UTF-16LE",
  "UTF-16BE",
] as const

const DELIMITER_PRESETS: { label: string; value: string }[] = [
  { label: "Comma (,)", value: "," },
  { label: "Tab (\\t)", value: "\t" },
  { label: "Semicolon (;)", value: ";" },
  { label: "Pipe (|)", value: "|" },
]

type CsvViewerProps = {
  /** Raw file URL to fetch the CSV/TSV data from. */
  url: string
  /** Default delimiter – "," for CSV, "\t" for TSV. */
  defaultDelimiter: string
}

export function CsvViewer({ url, defaultDelimiter }: CsvViewerProps) {
  const [encoding, setEncoding] = useState("UTF-8")
  const [delimiter, setDelimiter] = useState(defaultDelimiter)
  const [customDelimiter, setCustomDelimiter] = useState("")
  const [isCustom, setIsCustom] = useState(false)

  const [rows, setRows] = useState<string[][]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const effectiveDelimiter = isCustom ? customDelimiter : delimiter

  const fetchAndParse = useCallback(
    async (enc: string, delim: string) => {
      setIsLoading(true)
      setError(null)
      setRows([])
      try {
        const res = await fetch(url)
        if (!res.ok) throw new Error(`Failed to fetch file (${res.status})`)
        const buf = await res.arrayBuffer()
        const decoded = new TextDecoder(enc).decode(buf)
        const result = Papa.parse<string[]>(decoded, {
          delimiter: delim,
          header: false,
          skipEmptyLines: true,
        })
        if (result.errors.length > 0) {
          console.warn("CSV parse warnings:", result.errors)
        }
        setRows(result.data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load file")
      } finally {
        setIsLoading(false)
      }
    },
    [url],
  )

  // Initial load
  useEffect(() => {
    fetchAndParse(encoding, effectiveDelimiter)
    // Only run on mount / url change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  function handleRefresh() {
    fetchAndParse(encoding, effectiveDelimiter)
  }

  const headerRow = rows[0]
  const dataRows = rows.slice(1)

  // Column count for proper rendering
  const columnCount = useMemo(() => {
    if (!rows.length) return 0
    return Math.max(...rows.map((r) => r.length))
  }, [rows])

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Controls */}
      <div className="flex items-end gap-3 flex-wrap">
        <div className="space-y-1">
          <Label className="text-xs">Encoding</Label>
          <Select value={encoding} onValueChange={setEncoding}>
            <SelectTrigger className="w-[130px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ENCODINGS.map((enc) => (
                <SelectItem key={enc} value={enc} className="text-xs">
                  {enc}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Delimiter</Label>
          <Select
            value={isCustom ? "__custom__" : delimiter}
            onValueChange={(v) => {
              if (v === "__custom__") {
                setIsCustom(true)
              } else {
                setIsCustom(false)
                setDelimiter(v)
              }
            }}
          >
            <SelectTrigger className="w-[150px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DELIMITER_PRESETS.map((p) => (
                <SelectItem key={p.value} value={p.value} className="text-xs">
                  {p.label}
                </SelectItem>
              ))}
              <SelectItem value="__custom__" className="text-xs">
                Custom...
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {isCustom && (
          <div className="space-y-1">
            <Label className="text-xs">Custom</Label>
            <Input
              value={customDelimiter}
              onChange={(e) => setCustomDelimiter(e.target.value)}
              placeholder="e.g. :"
              className="w-[80px] h-8 text-xs font-mono"
            />
          </div>
        )}

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={isLoading}
          className="h-8"
        >
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          Refresh
        </Button>

        {!isLoading && rows.length > 0 && (
          <span className="text-xs text-muted-foreground ml-auto">
            {dataRows.length} rows · {columnCount} columns
          </span>
        )}
      </div>

      {/* Table */}
      {isLoading && (
        <div className="flex items-center justify-center h-[400px]">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {error && (
        <div className="flex items-center justify-center h-[200px]">
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      )}

      {!isLoading && !error && rows.length > 0 && (
        <div className="border rounded overflow-auto flex-1 min-h-0 max-h-[500px]">
          <table className="w-full text-xs font-mono border-collapse">
            <thead className="bg-muted/60 sticky top-0 z-10">
              <tr>
                <th className="px-2 py-1.5 text-right text-muted-foreground border-r w-10 font-medium">
                  #
                </th>
                {headerRow?.map((cell, i) => (
                  <th
                    key={i}
                    className="px-2 py-1.5 text-left font-semibold border-r last:border-r-0 whitespace-nowrap"
                  >
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {dataRows.map((row, ri) => (
                <tr key={ri} className="hover:bg-muted/30">
                  <td className="px-2 py-1 text-right text-muted-foreground border-r tabular-nums">
                    {ri + 1}
                  </td>
                  {Array.from({ length: columnCount }, (_, ci) => (
                    <td
                      key={ci}
                      className="px-2 py-1 border-r last:border-r-0 whitespace-nowrap max-w-[300px] truncate"
                      title={row[ci] ?? ""}
                    >
                      {row[ci] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!isLoading && !error && rows.length === 0 && (
        <div className="flex items-center justify-center h-[200px]">
          <p className="text-sm text-muted-foreground">No data</p>
        </div>
      )}
    </div>
  )
}
