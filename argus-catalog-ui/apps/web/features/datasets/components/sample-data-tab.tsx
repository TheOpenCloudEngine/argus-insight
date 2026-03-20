"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Papa from "papaparse"
import { Loader2, RefreshCw, Save, Trash2, Upload } from "lucide-react"
import { toast } from "sonner"

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
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  deleteSampleData,
  fetchDelimiterConfig,
  fetchSampleData,
  saveDelimiterConfig,
  uploadSampleData,
} from "@/features/datasets/api"

// ---------------------------------------------------------------------------
// Constants (matches argus-insight-ui csv-viewer)
// ---------------------------------------------------------------------------

const ENCODINGS: { label: string; value: string }[] = [
  { label: "UTF-8", value: "UTF-8" },
  { label: "EUC-KR", value: "EUC-KR" },
  { label: "MS949 (CP949)", value: "windows-949" },
  { label: "ISO-8859-1", value: "ISO-8859-1" },
  { label: "Shift_JIS", value: "Shift_JIS" },
  { label: "Windows-1252", value: "Windows-1252" },
  { label: "UTF-16LE", value: "UTF-16LE" },
  { label: "UTF-16BE", value: "UTF-16BE" },
]

const LINE_DELIMITERS: { label: string; value: string }[] = [
  { label: "\\n (LF)", value: "\n" },
  { label: "\\r\\n (CRLF)", value: "\r\n" },
]

const DELIMITER_PRESETS: { label: string; value: string }[] = [
  { label: "Comma (,)", value: "," },
  { label: "Tab (\\t)", value: "\t" },
  { label: "Semicolon (;)", value: ";" },
  { label: "Pipe (|)", value: "|" },
]

const MAX_FILE_SIZE = 100 * 1024 // 100 KB

const DELIM_ESCAPE = "__escape__"
const DELIM_CUSTOM = "__custom__"
const NO_QUOTE = "__none__"

function parseEscapeSequences(input: string): string {
  return input.replace(
    /\\x([0-9A-Fa-f]{2})|\\u([0-9A-Fa-f]{4})|\\([nrt0\\])/g,
    (_, hex2, hex4, simple) => {
      if (hex2) return String.fromCharCode(parseInt(hex2, 16))
      if (hex4) return String.fromCharCode(parseInt(hex4, 16))
      switch (simple) {
        case "n": return "\n"
        case "r": return "\r"
        case "t": return "\t"
        case "0": return "\0"
        case "\\": return "\\"
        default: return simple
      }
    },
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type SampleDataTabProps = {
  datasetId: number
}

export function SampleDataTab({ datasetId }: SampleDataTabProps) {
  // CSV parse settings
  const [encoding, setEncoding] = useState("UTF-8")
  const [lineDelimiter, setLineDelimiter] = useState("\n")
  const [delimiter, setDelimiter] = useState(",")
  const [delimiterMode, setDelimiterMode] = useState<null | "escape" | "custom">(null)
  const [delimiterInput, setDelimiterInput] = useState("")
  const [hasHeader, setHasHeader] = useState(true)
  const [quoteChar, setQuoteChar] = useState(NO_QUOTE)
  const [customQuoteChar, setCustomQuoteChar] = useState("")
  const [isCustomQuote, setIsCustomQuote] = useState(false)

  // Data state
  const [rows, setRows] = useState<string[][]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSample, setHasSample] = useState<boolean | null>(null)

  // Upload state
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Derived delimiter values
  const effectiveDelimiter = useMemo(() => {
    if (delimiterMode === "escape") {
      const parsed = parseEscapeSequences(delimiterInput)
      return parsed.charAt(0) || delimiter
    }
    if (delimiterMode === "custom") {
      return delimiterInput.charAt(0) || delimiter
    }
    return delimiter
  }, [delimiterMode, delimiterInput, delimiter])

  const effectiveEscapeChar = useMemo(() => {
    if (delimiterMode === "escape" && delimiterInput) {
      return parseEscapeSequences(delimiterInput).charAt(0) || undefined
    }
    return undefined
  }, [delimiterMode, delimiterInput])

  const effectiveQuoteChar = useMemo(() => {
    if (isCustomQuote) return customQuoteChar || false
    if (quoteChar === NO_QUOTE) return false
    return quoteChar
  }, [isCustomQuote, customQuoteChar, quoteChar])

  const delimiterSelectValue = useMemo(() => {
    if (delimiterMode === "escape") return DELIM_ESCAPE
    if (delimiterMode === "custom") return DELIM_CUSTOM
    return delimiter
  }, [delimiterMode, delimiter])

  // ---------------------------------------------------------------------------
  // Parse raw CSV text with current settings
  // ---------------------------------------------------------------------------
  const parseCsv = useCallback(
    (buf: ArrayBuffer, enc: string, delim: string, escape: string | undefined, quote: string | false, lineDelim: string) => {
      try {
        let decoded = new TextDecoder(enc).decode(buf)

        if (lineDelim === "\n") {
          decoded = decoded.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
        } else {
          decoded = decoded.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\n/g, "\r\n")
        }

        const parseConfig: Papa.ParseConfig = {
          delimiter: delim,
          newline: lineDelim,
          header: false,
          skipEmptyLines: true,
        }
        if (escape) parseConfig.escapeChar = escape
        if (quote !== false) {
          parseConfig.quoteChar = quote
        } else {
          parseConfig.quoteChar = "\0"
        }

        const result = Papa.parse<string[]>(decoded, parseConfig)
        if (result.errors.length > 0) {
          console.warn("CSV parse warnings:", result.errors)
        }
        setRows(result.data)
        setError(null)
      } catch {
        setError("Unable to display sample data. The file may be corrupted or use an unsupported format.")
        setRows([])
      }
    },
    [],
  )

  // Keep raw buffer for re-parsing with different settings
  const rawBufferRef = useRef<ArrayBuffer | null>(null)

  // ---------------------------------------------------------------------------
  // Fetch sample from server
  // ---------------------------------------------------------------------------
  const loadSample = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    setRows([])
    try {
      const res = await fetchSampleData(datasetId)
      if (res.status === 404) {
        setHasSample(false)
        rawBufferRef.current = null
        return
      }
      if (!res.ok) throw new Error(`Failed to fetch sample (${res.status})`)
      const buf = await res.arrayBuffer()
      rawBufferRef.current = buf
      setHasSample(true)
      parseCsv(buf, encoding, effectiveDelimiter, effectiveEscapeChar, effectiveQuoteChar, lineDelimiter)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sample data")
      setHasSample(false)
    } finally {
      setIsLoading(false)
    }
    // Only re-fetch from server on mount / datasetId change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, parseCsv])

  useEffect(() => {
    loadSample()
  }, [loadSample])

  // ---------------------------------------------------------------------------
  // Load delimiter config from server (if exists) and re-parse
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetchDelimiterConfig(datasetId)
        if (!res.ok || cancelled) return
        const cfg = await res.json()
        const enc = cfg.encoding ?? "UTF-8"
        const lineDel = cfg.line_delimiter ?? "\n"
        const del = cfg.delimiter ?? ","
        const delMode: "escape" | "custom" | null = cfg.delimiter_mode ?? null
        const delInput = cfg.delimiter_input ?? ""
        const header = cfg.has_header ?? true
        const qChar = cfg.quote_char ?? NO_QUOTE
        const cqChar = cfg.custom_quote_char ?? ""
        const isCQ = cfg.is_custom_quote ?? false

        setEncoding(enc)
        setLineDelimiter(lineDel)
        setDelimiter(del)
        setDelimiterMode(delMode)
        setDelimiterInput(delInput)
        setHasHeader(header)
        setQuoteChar(qChar)
        setCustomQuoteChar(cqChar)
        setIsCustomQuote(isCQ)

        // Re-parse with loaded config if buffer is available
        if (rawBufferRef.current) {
          let effDelim = del
          if (delMode === "escape") {
            const parsed = parseEscapeSequences(delInput)
            effDelim = parsed.charAt(0) || del
          } else if (delMode === "custom") {
            effDelim = delInput.charAt(0) || del
          }
          const effEscape = delMode === "escape" && delInput
            ? parseEscapeSequences(delInput).charAt(0) || undefined
            : undefined
          let effQuote: string | false
          if (isCQ) effQuote = cqChar || false
          else if (qChar === NO_QUOTE) effQuote = false
          else effQuote = qChar

          parseCsv(rawBufferRef.current, enc, effDelim, effEscape, effQuote, lineDel)
        }
      } catch {
        // no config saved yet – use defaults
      }
    })()
    return () => { cancelled = true }
  }, [datasetId, parseCsv])

  // ---------------------------------------------------------------------------
  // Save delimiter config to server
  // ---------------------------------------------------------------------------
  const handleSave = async () => {
    setSaving(true)
    try {
      await saveDelimiterConfig(datasetId, {
        encoding,
        line_delimiter: lineDelimiter,
        delimiter,
        delimiter_mode: delimiterMode,
        delimiter_input: delimiterInput,
        has_header: hasHeader,
        quote_char: quoteChar,
        custom_quote_char: customQuoteChar,
        is_custom_quote: isCustomQuote,
      })
      toast.success("CSV parsing options have been saved.")
    } catch (err) {
      console.error("Failed to save delimiter config:", err)
      toast.error("Failed to save CSV parsing options.")
    } finally {
      setSaving(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Re-parse with current settings (no server call)
  // ---------------------------------------------------------------------------
  const handleRefresh = () => {
    if (rawBufferRef.current) {
      parseCsv(rawBufferRef.current, encoding, effectiveDelimiter, effectiveEscapeChar, effectiveQuoteChar, lineDelimiter)
    } else {
      loadSample()
    }
  }

  // ---------------------------------------------------------------------------
  // Upload
  // ---------------------------------------------------------------------------
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    // Reset the input so the same file can be re-selected
    e.target.value = ""

    if (file.size > MAX_FILE_SIZE) {
      setUploadError(`File size (${(file.size / 1024).toFixed(1)} KB) exceeds the 100 KB limit.`)
      return
    }

    setUploading(true)
    setUploadError(null)
    try {
      await uploadSampleData(datasetId, file)
      // Reload
      await loadSample()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Delete
  // ---------------------------------------------------------------------------
  const handleDelete = async () => {
    try {
      await deleteSampleData(datasetId)
      setHasSample(false)
      setRows([])
      rawBufferRef.current = null
      setError(null)
    } catch {
      // ignore
    }
  }

  // ---------------------------------------------------------------------------
  // Display helpers
  // ---------------------------------------------------------------------------
  const displayRows = useMemo(() => {
    if (!rows.length) return { header: undefined, data: [], allRows: rows }
    if (hasHeader) {
      return { header: rows[0], data: rows.slice(1), allRows: rows }
    }
    return { header: undefined, data: rows, allRows: rows }
  }, [rows, hasHeader])

  const columnCount = useMemo(() => {
    if (!rows.length) return 0
    return Math.max(...rows.map((r) => r.length))
  }, [rows])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between py-3">
        <CardTitle className="text-base">Sample Data</CardTitle>
        <div className="flex items-center gap-2">
          {hasSample && (
            <Button size="sm" variant="outline" onClick={handleDelete} className="text-destructive">
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              Delete
            </Button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.tsv"
            className="hidden"
            onChange={handleFileSelect}
          />
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {/* Show controls + table when sample data exists */}
        {hasSample && (
          <div className="flex flex-col gap-3 p-4 text-sm">
            {/* CSV Parse Controls */}
            <div className="flex items-end gap-3 flex-wrap">
              <div className="space-y-1">
                <Label className="text-sm">Encoding</Label>
                <Select value={encoding} onValueChange={setEncoding}>
                  <SelectTrigger className="w-[130px] h-8 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ENCODINGS.map((enc) => (
                      <SelectItem key={enc.value} value={enc.value} className="text-sm">
                        {enc.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-sm">Line Delimiter</Label>
                <Select value={lineDelimiter} onValueChange={setLineDelimiter}>
                  <SelectTrigger className="w-[130px] h-8 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LINE_DELIMITERS.map((ld) => (
                      <SelectItem key={ld.value} value={ld.value} className="text-sm">
                        {ld.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-sm">Delimiter</Label>
                <div className="flex items-center gap-1.5">
                  <Select
                    value={delimiterSelectValue}
                    onValueChange={(v) => {
                      if (v === DELIM_ESCAPE) {
                        setDelimiterMode("escape")
                        setDelimiterInput("")
                      } else if (v === DELIM_CUSTOM) {
                        setDelimiterMode("custom")
                        setDelimiterInput("")
                      } else {
                        setDelimiterMode(null)
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
                      <SelectItem value={DELIM_ESCAPE} className="text-sm">
                        Escape
                      </SelectItem>
                      <SelectItem value={DELIM_CUSTOM} className="text-sm">
                        Custom...
                      </SelectItem>
                    </SelectContent>
                  </Select>

                  {delimiterMode === "escape" && (
                    <Input
                      value={delimiterInput}
                      onChange={(e) => setDelimiterInput(e.target.value)}
                      placeholder="e.g. \x1b"
                      className="w-[100px] h-8 text-sm font-mono"
                    />
                  )}

                  {delimiterMode === "custom" && (
                    <Input
                      value={delimiterInput}
                      onChange={(e) => setDelimiterInput(e.target.value.slice(0, 1))}
                      placeholder="e.g. :"
                      className="w-[80px] h-8 text-sm font-mono"
                      maxLength={1}
                    />
                  )}
                </div>
              </div>

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
                <Label className="text-sm">Quote</Label>
                <div className="flex items-center gap-1.5">
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

                  {isCustomQuote && (
                    <Input
                      value={customQuoteChar}
                      onChange={(e) => setCustomQuoteChar(e.target.value.slice(0, 1))}
                      placeholder="e.g. `"
                      className="w-[80px] h-8 text-sm font-mono"
                      maxLength={1}
                    />
                  )}
                </div>
              </div>

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

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSave}
                disabled={saving}
                className="h-8"
              >
                {saving ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5 mr-1.5" />
                )}
                Save
              </Button>

              {!isLoading && rows.length > 0 && (
                <span className="text-sm text-muted-foreground ml-auto">
                  {displayRows.data.length} rows · {columnCount} columns
                </span>
              )}
            </div>

            {/* Table */}
            {isLoading && (
              <div className="flex items-center justify-center h-[200px]">
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
                <table className="w-full text-sm font-mono border-collapse">
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
        )}

        {/* Empty state: no sample file */}
        {hasSample === false && (
          <div className="flex flex-col items-center justify-center gap-4 p-8">
            {uploadError && (
              <p className="text-sm text-destructive">{uploadError}</p>
            )}
            <div
              className="flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-lg p-8 w-full cursor-pointer hover:border-primary/50 hover:bg-muted/30 transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm font-medium">
                {uploading ? "Uploading..." : "Click to upload a CSV file"}
              </p>
              <p className="text-xs text-muted-foreground">
                Supported formats: .csv, .tsv (max 100 KB)
              </p>
            </div>
          </div>
        )}

        {/* Initial loading */}
        {hasSample === null && isLoading && (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
