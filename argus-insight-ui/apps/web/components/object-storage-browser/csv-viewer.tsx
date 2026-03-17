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

/** Sentinel value used by the Select component to represent "no quote character". */
const NO_QUOTE = "__none__"

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
  const [isCustomDelimiter, setIsCustomDelimiter] = useState(false)

  const [hasHeader, setHasHeader] = useState(true)
  const [escapeChar, setEscapeChar] = useState("")
  const [quoteChar, setQuoteChar] = useState(NO_QUOTE)
  const [customQuoteChar, setCustomQuoteChar] = useState("")
  const [isCustomQuote, setIsCustomQuote] = useState(false)

  const [rows, setRows] = useState<string[][]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const effectiveDelimiter = isCustomDelimiter ? customDelimiter : delimiter

  const effectiveQuoteChar = useMemo(() => {
    if (isCustomQuote) return customQuoteChar || false
    if (quoteChar === NO_QUOTE) return false
    return quoteChar
  }, [isCustomQuote, customQuoteChar, quoteChar])

  const fetchAndParse = useCallback(
    async (enc: string, delim: string, escape: string, quote: string | false) => {
      setIsLoading(true)
      setError(null)
      setRows([])
      try {
        const res = await fetch(url)
        if (!res.ok) throw new Error(`Failed to fetch file (${res.status})`)
        const buf = await res.arrayBuffer()
        const decoded = new TextDecoder(enc).decode(buf)

        const parseConfig: Papa.ParseConfig = {
          delimiter: delim,
          header: false,
          skipEmptyLines: true,
        }

        if (escape) {
          parseConfig.escapeChar = escape
        }

        if (quote !== false) {
          parseConfig.quoteChar = quote
        } else {
          // Disable quoting entirely
          parseConfig.quoteChar = "\0"
        }

        const result = Papa.parse<string[]>(decoded, parseConfig)
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
    fetchAndParse(encoding, effectiveDelimiter, escapeChar, effectiveQuoteChar)
    // Only run on mount / url change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  function handleRefresh() {
    fetchAndParse(encoding, effectiveDelimiter, escapeChar, effectiveQuoteChar)
  }

  const displayRows = useMemo(() => {
    if (!rows.length) return { header: undefined, data: [], allRows: rows }
    if (hasHeader) {
      return { header: rows[0], data: rows.slice(1), allRows: rows }
    }
    return { header: undefined, data: rows, allRows: rows }
  }, [rows, hasHeader])

  // Column count for proper rendering
  const columnCount = useMemo(() => {
    if (!rows.length) return 0
    return Math.max(...rows.map((r) => r.length))
  }, [rows])

  return (
    <div className="flex flex-col gap-3 h-full text-sm">
      {/* Controls – Row 1 */}
      <div className="flex items-end gap-3 flex-wrap">
        <div className="space-y-1">
          <Label className="text-sm">Encoding</Label>
          <Select value={encoding} onValueChange={setEncoding}>
            <SelectTrigger className="w-[130px] h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ENCODINGS.map((enc) => (
                <SelectItem key={enc} value={enc} className="text-sm">
                  {enc}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-sm">Delimiter</Label>
          <Select
            value={isCustomDelimiter ? "__custom__" : delimiter}
            onValueChange={(v) => {
              if (v === "__custom__") {
                setIsCustomDelimiter(true)
              } else {
                setIsCustomDelimiter(false)
                setDelimiter(v)
              }
            }}
          >
            <SelectTrigger className="w-[150px] h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DELIMITER_PRESETS.map((p) => (
                <SelectItem key={p.value} value={p.value} className="text-sm">
                  {p.label}
                </SelectItem>
              ))}
              <SelectItem value="__custom__" className="text-sm">
                Custom...
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {isCustomDelimiter && (
          <div className="space-y-1">
            <Label className="text-sm">Custom Delimiter</Label>
            <Input
              value={customDelimiter}
              onChange={(e) => setCustomDelimiter(e.target.value)}
              placeholder="e.g. :"
              className="w-[80px] h-8 text-sm font-[D2Coding,monospace]"
            />
          </div>
        )}

        <div className="space-y-1">
          <Label className="text-sm">Header</Label>
          <Select value={hasHeader ? "yes" : "no"} onValueChange={(v) => setHasHeader(v === "yes")}>
            <SelectTrigger className="w-[120px] h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="yes" className="text-sm">With Header</SelectItem>
              <SelectItem value="no" className="text-sm">No Header</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-sm">Escape</Label>
          <Input
            value={escapeChar}
            onChange={(e) => setEscapeChar(e.target.value.slice(0, 1))}
            placeholder="None"
            className="w-[70px] h-8 text-sm font-[D2Coding,monospace]"
            maxLength={1}
          />
        </div>

        <div className="space-y-1">
          <Label className="text-sm">Quote</Label>
          <Select
            value={isCustomQuote ? "__custom__" : quoteChar}
            onValueChange={(v) => {
              if (v === "__custom__") {
                setIsCustomQuote(true)
              } else {
                setIsCustomQuote(false)
                setQuoteChar(v)
              }
            }}
          >
            <SelectTrigger className="w-[120px] h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_QUOTE} className="text-sm">None</SelectItem>
              <SelectItem value={'"'} className="text-sm">Double (&quot;)</SelectItem>
              <SelectItem value="'" className="text-sm">Single (&apos;)</SelectItem>
              <SelectItem value="__custom__" className="text-sm">Custom...</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {isCustomQuote && (
          <div className="space-y-1">
            <Label className="text-sm">Custom Quote</Label>
            <Input
              value={customQuoteChar}
              onChange={(e) => setCustomQuoteChar(e.target.value.slice(0, 1))}
              placeholder="e.g. `"
              className="w-[80px] h-8 text-sm font-[D2Coding,monospace]"
              maxLength={1}
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
          <span className="text-sm text-muted-foreground ml-auto">
            {displayRows.data.length} rows · {columnCount} columns
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
          <table className="w-full text-sm font-[D2Coding,monospace] border-collapse">
            {displayRows.header && (
              <thead className="bg-muted/60 sticky top-0 z-10">
                <tr>
                  <th className="px-2 py-1.5 text-right text-muted-foreground border-r w-10 font-medium">
                    #
                  </th>
                  {displayRows.header.map((cell, i) => (
                    <th
                      key={i}
                      className="px-2 py-1.5 text-left font-semibold border-r last:border-r-0 whitespace-nowrap"
                    >
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody className="divide-y">
              {displayRows.data.map((row, ri) => (
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
