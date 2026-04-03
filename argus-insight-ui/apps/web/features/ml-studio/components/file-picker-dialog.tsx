"use client"

import { useCallback, useEffect, useState } from "react"
import {
  ChevronRight,
  File,
  FileSpreadsheet,
  Folder,
  HardDrive,
  Loader2,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"

import { authFetch } from "@/features/auth/auth-fetch"

// ── Types ─────────────────────────────────────────────────

interface BucketItem {
  name: string
}

interface FolderItem {
  prefix: string
  name: string
}

interface ObjectItem {
  key: string
  size: number
  last_modified: string
}

interface FilePickerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelect: (bucket: string, path: string) => void
  fileFilter?: string[]
}

// ── Helpers ───────────────────────────────────────────────

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function getFileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase()
  if (["csv", "tsv", "parquet", "xlsx", "xls"].includes(ext || "")) {
    return <FileSpreadsheet className="h-4 w-4 text-green-600" />
  }
  return <File className="h-4 w-4 text-muted-foreground" />
}

// ── Component ─────────────────────────────────────────────

export function FilePickerDialog({
  open,
  onOpenChange,
  onSelect,
  fileFilter = [".csv", ".parquet", ".tsv", ".xlsx", ".xls"],
}: FilePickerDialogProps) {
  const [buckets, setBuckets] = useState<BucketItem[]>([])
  const [selectedBucket, setSelectedBucket] = useState("")
  const [prefix, setPrefix] = useState("")
  const [folders, setFolders] = useState<FolderItem[]>([])
  const [objects, setObjects] = useState<ObjectItem[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [continuationToken, setContinuationToken] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)

  // Load buckets
  useEffect(() => {
    if (!open) return
    authFetch("/api/v1/objectfilemgr/buckets")
      .then((r) => (r.ok ? r.json() : { buckets: [] }))
      .then((data) => setBuckets(data.buckets ?? []))
      .catch(() => {})
  }, [open])

  // Load objects
  const loadObjects = useCallback(async (append = false) => {
    if (!selectedBucket) return
    if (append) setLoadingMore(true)
    else setLoading(true)

    try {
      const params = new URLSearchParams({
        bucket: selectedBucket,
        prefix,
        delimiter: "/",
        max_keys: "100",
      })
      if (append && continuationToken) {
        params.set("continuation_token", continuationToken)
      }

      const res = await authFetch(`/api/v1/objectfilemgr/objects?${params}`)
      if (res.ok) {
        const data = await res.json()
        const newFolders: FolderItem[] = data.folders ?? []
        const allObjects: ObjectItem[] = data.objects ?? []
        const filtered = fileFilter.length > 0
          ? allObjects.filter((o) => fileFilter.some((ext) => o.key.toLowerCase().endsWith(ext)))
          : allObjects

        if (append) {
          setFolders((prev) => [...prev, ...newFolders])
          setObjects((prev) => [...prev, ...filtered])
        } else {
          setFolders(newFolders)
          setObjects(filtered)
        }
        setContinuationToken(data.next_continuation_token || null)
        setHasMore(!!data.is_truncated)
      }
    } catch { /* ignore */ }
    finally {
      setLoading(false)
      setLoadingMore(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBucket, prefix, continuationToken])

  // Reset and load on bucket/prefix change
  useEffect(() => {
    if (!selectedBucket) return
    setContinuationToken(null)
    setHasMore(false)
    setFolders([])
    setObjects([])
    loadObjects(false)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBucket, prefix])

  const enterFolder = (folderPrefix: string) => setPrefix(folderPrefix)

  const goUp = () => {
    const parts = prefix.replace(/\/$/, "").split("/")
    parts.pop()
    setPrefix(parts.length > 0 ? parts.join("/") + "/" : "")
  }

  const selectFile = (key: string) => {
    onSelect(selectedBucket, key)
    onOpenChange(false)
  }

  const pathParts = prefix ? prefix.replace(/\/$/, "").split("/") : []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm">Select Data File</DialogTitle>
          <DialogDescription className="text-sm">
            Browse MinIO storage and select a data file (CSV, Parquet, TSV, Excel)
          </DialogDescription>
        </DialogHeader>

        {/* Bucket selector + breadcrumb */}
        <div className="flex items-center gap-2 text-sm flex-wrap pb-2">
          <select
            value={selectedBucket}
            onChange={(e) => { setSelectedBucket(e.target.value); setPrefix("") }}
            className="h-8 rounded-md border bg-background px-2 text-sm"
          >
            <option value="">Select bucket...</option>
            {buckets.map((b) => (
              <option key={b.name} value={b.name}>{b.name}</option>
            ))}
          </select>

          {selectedBucket && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <button type="button" className="hover:text-foreground" onClick={() => setPrefix("")}>
                <HardDrive className="h-3 w-3" />
              </button>
              {pathParts.map((part, i) => (
                <span key={i} className="flex items-center gap-1">
                  <ChevronRight className="h-3 w-3" />
                  <button
                    type="button"
                    className="hover:text-foreground hover:underline"
                    onClick={() => setPrefix(pathParts.slice(0, i + 1).join("/") + "/")}
                  >
                    {part}
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* File list — fixed height with scroll */}
        <div className="h-[400px] overflow-y-auto rounded-lg border">
          {!selectedBucket ? (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              Select a bucket to browse files
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : folders.length === 0 && objects.length === 0 ? (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              {prefix ? "Empty folder" : "Empty bucket"}
            </div>
          ) : (
            <div className="divide-y">
              {/* Back */}
              {prefix && (
                <button
                  type="button"
                  onClick={goUp}
                  className="flex w-full items-center gap-3 px-4 py-2 text-sm hover:bg-muted/50"
                >
                  <Folder className="h-4 w-4 text-muted-foreground" />
                  <span className="text-muted-foreground">..</span>
                </button>
              )}

              {/* Folders */}
              {folders.map((f) => (
                <button
                  key={f.prefix}
                  type="button"
                  onClick={() => enterFolder(f.prefix)}
                  className="flex w-full items-center gap-3 px-4 py-2 text-sm hover:bg-muted/50"
                >
                  <Folder className="h-4 w-4 text-blue-500" />
                  <span>{f.name}</span>
                </button>
              ))}

              {/* Files */}
              {objects.map((o) => {
                const name = o.key.split("/").pop() || o.key
                return (
                  <button
                    key={o.key}
                    type="button"
                    onClick={() => selectFile(o.key)}
                    className="flex w-full items-center gap-3 px-4 py-2 text-sm hover:bg-primary/5 hover:text-primary"
                  >
                    {getFileIcon(name)}
                    <span className="flex-1 text-left truncate">{name}</span>
                    <span className="text-xs text-muted-foreground shrink-0">{formatSize(o.size)}</span>
                  </button>
                )
              })}

              {/* Load More */}
              {hasMore && (
                <div className="flex justify-center py-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs"
                    disabled={loadingMore}
                    onClick={() => loadObjects(true)}
                  >
                    {loadingMore ? <Loader2 className="mr-1.5 h-3 w-3 animate-spin" /> : null}
                    Load More
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-muted-foreground">
            {folders.length} folders, {objects.length} files
          </span>
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
