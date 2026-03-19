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
    // Download ZIP from server endpoint (proper ZIP with CRC32)
    const a = document.createElement("a")
    a.href = "/api/v1/dns/zone/bind-config/download"
    a.download = ""
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="overflow-y-auto px-5"
        style={{ width: 640, maxWidth: "none" }}
      >
        <SheetHeader className="pb-4">
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
          </div>
          {data && !loading && (
            <div className="flex justify-end pt-2">
              <Button size="sm" onClick={handleExport}>
                <Download className="mr-1.5 h-4 w-4" />
                Export
              </Button>
            </div>
          )}
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
