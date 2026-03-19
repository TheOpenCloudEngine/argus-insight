/**
 * BIND Configuration Export Sheet dialog.
 *
 * Opens a side panel that fetches and displays BIND configuration files
 * (named.conf.local and zone data file) for the configured DNS zone.
 * Includes an Export button to download all files as a ZIP archive.
 */

"use client"

import { useCallback, useEffect, useState } from "react"
import { Download, FileCode2, Loader2 } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@workspace/ui/components/sheet"
import { Button } from "@workspace/ui/components/button"
import { CodeViewer } from "@/components/code-viewer"
import { type BindConfigFile, type BindConfigResponse, fetchBindConfig } from "../api"

type DnsZoneBindDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const filePathHints: Record<string, string> = {
  "named.conf.local": "/etc/bind/named.conf.local",
}

function getFilePathHint(filename: string): string {
  if (filePathHints[filename]) return filePathHints[filename]
  if (filename.startsWith("db.")) return `/etc/bind/zones/${filename}`
  return ""
}

/**
 * Create a ZIP file in the browser from the config files and trigger download.
 * Uses a minimal ZIP implementation (no external library needed).
 */
async function downloadAsZip(zone: string, files: BindConfigFile[]) {
  // Use JSZip-like manual construction for simple text files
  // Each file entry: local file header + data + central directory
  const encoder = new TextEncoder()
  const parts: Uint8Array[] = []
  const centralDir: Uint8Array[] = []
  let offset = 0

  for (const file of files) {
    const nameBytes = encoder.encode(file.filename)
    const dataBytes = encoder.encode(file.content)

    // Local file header (30 + nameLen bytes)
    const localHeader = new Uint8Array(30 + nameBytes.length)
    const lv = new DataView(localHeader.buffer)
    lv.setUint32(0, 0x04034b50, true)  // signature
    lv.setUint16(4, 20, true)           // version needed
    lv.setUint16(6, 0, true)            // flags
    lv.setUint16(8, 0, true)            // compression (store)
    lv.setUint16(10, 0, true)           // mod time
    lv.setUint16(12, 0, true)           // mod date
    lv.setUint32(14, 0, true)           // crc32 (0 for simplicity)
    lv.setUint32(18, dataBytes.length, true)  // compressed size
    lv.setUint32(22, dataBytes.length, true)  // uncompressed size
    lv.setUint16(26, nameBytes.length, true)  // filename length
    lv.setUint16(28, 0, true)           // extra field length
    localHeader.set(nameBytes, 30)

    // Central directory entry (46 + nameLen bytes)
    const cdEntry = new Uint8Array(46 + nameBytes.length)
    const cv = new DataView(cdEntry.buffer)
    cv.setUint32(0, 0x02014b50, true)   // signature
    cv.setUint16(4, 20, true)           // version made by
    cv.setUint16(6, 20, true)           // version needed
    cv.setUint16(8, 0, true)            // flags
    cv.setUint16(10, 0, true)           // compression
    cv.setUint16(12, 0, true)           // mod time
    cv.setUint16(14, 0, true)           // mod date
    cv.setUint32(16, 0, true)           // crc32
    cv.setUint32(20, dataBytes.length, true)
    cv.setUint32(24, dataBytes.length, true)
    cv.setUint16(28, nameBytes.length, true)
    cv.setUint16(30, 0, true)           // extra field length
    cv.setUint16(32, 0, true)           // comment length
    cv.setUint16(34, 0, true)           // disk number
    cv.setUint16(36, 0, true)           // internal attrs
    cv.setUint32(38, 0, true)           // external attrs
    cv.setUint32(42, offset, true)      // local header offset
    cdEntry.set(nameBytes, 46)

    parts.push(localHeader, dataBytes)
    centralDir.push(cdEntry)
    offset += localHeader.length + dataBytes.length
  }

  // End of central directory
  const cdOffset = offset
  let cdSize = 0
  for (const cd of centralDir) cdSize += cd.length

  const eocd = new Uint8Array(22)
  const ev = new DataView(eocd.buffer)
  ev.setUint32(0, 0x06054b50, true)
  ev.setUint16(4, 0, true)
  ev.setUint16(6, 0, true)
  ev.setUint16(8, files.length, true)
  ev.setUint16(10, files.length, true)
  ev.setUint32(12, cdSize, true)
  ev.setUint32(16, cdOffset, true)
  ev.setUint16(20, 0, true)

  const blob = new Blob([...parts, ...centralDir, eocd], { type: "application/octet-stream" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `bind-${zone}.zip`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function DnsZoneBindDialog({ open, onOpenChange }: DnsZoneBindDialogProps) {
  const [data, setData] = useState<BindConfigResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchBindConfig()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load BIND configuration")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      loadConfig()
    } else {
      setData(null)
      setError(null)
    }
  }, [open, loadConfig])

  function handleExport() {
    if (data) {
      downloadAsZip(data.zone, data.files)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="overflow-y-auto px-5"
        style={{ width: 640, maxWidth: "none" }}
      >
        <SheetHeader>
          <div className="flex items-center justify-between">
            <div>
              <SheetTitle className="flex items-center gap-2">
                <FileCode2 className="h-5 w-5" />
                BIND Configuration Export
              </SheetTitle>
              <SheetDescription>
                {data ? `Zone: ${data.zone}` : "Loading..."}
              </SheetDescription>
            </div>
            {data && !loading && (
              <Button size="sm" variant="outline" onClick={handleExport}>
                <Download className="mr-1.5 h-4 w-4" />
                Export
              </Button>
            )}
          </div>
        </SheetHeader>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">
              Generating BIND configuration...
            </span>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {data && !loading && (
          <div className="space-y-6 pb-6">
            {data.files.map((file: BindConfigFile) => {
              const pathHint = getFilePathHint(file.filename)
              return (
                <div key={file.filename} className="space-y-2">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      {file.filename}
                    </h3>
                    {pathHint && (
                      <p className="text-xs text-muted-foreground font-mono">
                        {pathHint}
                      </p>
                    )}
                  </div>
                  <CodeViewer content={file.content} maxHeight="500px" />
                </div>
              )
            })}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
