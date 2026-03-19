/**
 * BIND Configuration Export Sheet dialog.
 *
 * Opens a right-side sliding panel (Sheet) that fetches and displays
 * BIND-compatible configuration files for the configured DNS zone.
 * The panel shows:
 *
 * 1. **named.conf.local** - Zone declaration file that tells BIND where
 *    to find the zone data file. Shows the expected path on a Linux system.
 *
 * 2. **db.{zone}** - Zone data file with all enabled DNS records formatted
 *    in standard BIND zone file syntax. Disabled records are excluded.
 *
 * Each file is displayed in a syntax-highlighted code viewer with its
 * expected filesystem path shown as a hint below the filename.
 *
 * The "Export" button triggers a browser download of all files packaged
 * as a ZIP archive via the backend's /dns/zone/bind-config/download endpoint.
 *
 * Data is fetched fresh each time the sheet opens and cleared when it closes.
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

/** Props for the DnsZoneBindDialog component. */
type DnsZoneBindDialogProps = {
  /** Whether the sheet is open */
  open: boolean
  /** Callback to open/close the sheet */
  onOpenChange: (open: boolean) => void
}

/**
 * Mapping of known filenames to their expected filesystem paths on a
 * typical Linux BIND installation. Shown as hints below each file header.
 */
const filePathHints: Record<string, string> = {
  "named.conf.local": "/etc/bind/named.conf.local",
}

/**
 * Get the expected filesystem path for a BIND config file.
 * Named.conf.local has a static path; zone data files (db.*) go in /etc/bind/zones/.
 *
 * @param filename - The filename to look up
 * @returns The expected filesystem path, or empty string if unknown
 */
function getFilePathHint(filename: string): string {
  if (filePathHints[filename]) return filePathHints[filename]
  if (filename.startsWith("db.")) return `/etc/bind/zones/${filename}`
  return ""
}

/**
 * Sheet panel component for previewing and exporting BIND configuration files.
 *
 * Fetches the configuration from the API when opened, displays each file
 * in a code viewer, and provides an Export button for ZIP download.
 */
export function DnsZoneBindDialog({ open, onOpenChange }: DnsZoneBindDialogProps) {
  const [data, setData] = useState<BindConfigResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /** Fetch BIND config files from the backend API. */
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

  // Fetch config when opened; clear data when closed to avoid showing stale content.
  useEffect(() => {
    if (open) {
      loadConfig()
    } else {
      setData(null)
      setError(null)
    }
  }, [open, loadConfig])

  /**
   * Trigger a browser download of the BIND config ZIP file.
   *
   * Creates a temporary anchor element pointing to the backend's ZIP
   * download endpoint, clicks it programmatically, then cleans up.
   * This approach avoids CORS issues since it navigates to the same origin.
   */
  function handleExport() {
    // Download ZIP from server endpoint (proper ZIP with deflate compression)
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
