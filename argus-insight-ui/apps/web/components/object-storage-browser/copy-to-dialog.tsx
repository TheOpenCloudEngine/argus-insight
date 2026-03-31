"use client"

import { useCallback, useEffect, useState } from "react"
import { CheckCircle2, ChevronRight, Folder, Loader2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Checkbox } from "@workspace/ui/components/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { crossCopyObjects, listBuckets, listObjects } from "@/features/object-storage/api"

interface CopyToDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sourceBucket: string
  sourceKeys: string[]
  onComplete: () => void
}

export function CopyToDialog({
  open,
  onOpenChange,
  sourceBucket,
  sourceKeys,
  onComplete,
}: CopyToDialogProps) {
  const [buckets, setBuckets] = useState<string[]>([])
  const [destBucket, setDestBucket] = useState("")
  const [destPrefix, setDestPrefix] = useState("")
  const [folders, setFolders] = useState<string[]>([])
  const [loadingFolders, setLoadingFolders] = useState(false)
  const [overwrite, setOverwrite] = useState(false)

  const [phase, setPhase] = useState<"select" | "copying" | "done" | "error">("select")
  const [copyResult, setCopyResult] = useState<{ copied: number; skipped: number; errors: string[] } | null>(null)

  // Load buckets
  useEffect(() => {
    if (!open) return
    setPhase("select")
    setCopyResult(null)
    setDestPrefix("")
    listBuckets()
      .then((data) => {
        const names = (data.buckets ?? []).map((b: { name: string }) => b.name)
        setBuckets(names)
        if (!destBucket && names.length > 0) setDestBucket(names[0])
      })
      .catch(() => setBuckets([]))
  }, [open])

  // Load folders when bucket or prefix changes
  const loadFolders = useCallback(async () => {
    if (!destBucket) return
    setLoadingFolders(true)
    try {
      const data = await listObjects(destBucket, destPrefix)
      const dirs = (data.common_prefixes ?? []).map((p: string) => p)
      setFolders(dirs)
    } catch {
      setFolders([])
    }
    setLoadingFolders(false)
  }, [destBucket, destPrefix])

  useEffect(() => { if (open && destBucket) loadFolders() }, [open, destBucket, destPrefix, loadFolders])

  const navigateToFolder = (folder: string) => {
    setDestPrefix(folder)
  }

  const navigateUp = () => {
    if (!destPrefix) return
    const parts = destPrefix.replace(/\/$/, "").split("/")
    parts.pop()
    setDestPrefix(parts.length > 0 ? parts.join("/") + "/" : "")
  }

  const handleCopy = async () => {
    setPhase("copying")
    try {
      const result = await crossCopyObjects(
        sourceBucket,
        sourceKeys,
        destBucket,
        destPrefix,
        overwrite,
      )
      setCopyResult({ copied: result.copied, skipped: result.skipped, errors: result.errors })
      setPhase("done")
      onComplete()
    } catch (e) {
      setCopyResult({ copied: 0, skipped: 0, errors: [e instanceof Error ? e.message : "Copy failed"] })
      setPhase("error")
    }
  }

  const fileCount = sourceKeys.length
  const displayPath = destPrefix || "/"

  return (
    <Dialog open={open} onOpenChange={(v) => { if (phase !== "copying") onOpenChange(v) }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {phase === "select" && "Copy to..."}
            {phase === "copying" && "Copying..."}
            {phase === "done" && "Copy Complete"}
            {phase === "error" && "Copy Failed"}
          </DialogTitle>
          {phase === "select" && (
            <DialogDescription>
              Copy {fileCount} {fileCount === 1 ? "item" : "items"} from {sourceBucket}
            </DialogDescription>
          )}
        </DialogHeader>

        {phase === "select" && (
          <div className="space-y-4">
            {/* Destination bucket */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium">Destination Bucket</label>
              <Select value={destBucket} onValueChange={(v) => { setDestBucket(v); setDestPrefix("") }}>
                <SelectTrigger>
                  <SelectValue placeholder="Select bucket..." />
                </SelectTrigger>
                <SelectContent>
                  {buckets.map((b) => (
                    <SelectItem key={b} value={b}>{b}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Folder browser */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium">Destination Path</label>
              <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                <button className="hover:underline" onClick={() => setDestPrefix("")}>{destBucket}</button>
                {destPrefix && destPrefix.split("/").filter(Boolean).map((part, i, arr) => {
                  const path = arr.slice(0, i + 1).join("/") + "/"
                  return (
                    <span key={path} className="flex items-center gap-1">
                      <ChevronRight className="h-3 w-3" />
                      <button className="hover:underline" onClick={() => setDestPrefix(path)}>{part}</button>
                    </span>
                  )
                })}
              </div>
              <div className="max-h-40 overflow-y-auto rounded-md border p-1">
                {destPrefix && (
                  <button
                    className="flex items-center gap-2 w-full rounded px-2 py-1.5 text-sm hover:bg-muted/50 text-muted-foreground"
                    onClick={navigateUp}
                  >
                    <Folder className="h-4 w-4" /> ..
                  </button>
                )}
                {loadingFolders ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                ) : folders.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-3">
                    {destPrefix ? "No subfolders" : "No folders"}. Files will be copied here.
                  </p>
                ) : (
                  folders.map((f) => {
                    const name = f.replace(/\/$/, "").split("/").pop() || f
                    return (
                      <button
                        key={f}
                        className="flex items-center gap-2 w-full rounded px-2 py-1.5 text-sm hover:bg-muted/50"
                        onClick={() => navigateToFolder(f)}
                      >
                        <Folder className="h-4 w-4 text-muted-foreground" /> {name}
                      </button>
                    )
                  })
                )}
              </div>
              <p className="text-xs text-muted-foreground">Selected: {displayPath}</p>
            </div>

            {/* Overwrite option */}
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={overwrite} onCheckedChange={(v) => setOverwrite(!!v)} />
              Overwrite existing files
            </label>
          </div>
        )}

        {phase === "copying" && (
          <div className="flex flex-col items-center gap-3 py-6">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Please wait a moment...</p>
          </div>
        )}

        {phase === "done" && copyResult && (
          <div className="space-y-2 py-2">
            <div className="rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-2 text-sm dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800">
              <CheckCircle2 className="inline h-4 w-4 mr-1.5" />
              {copyResult.copied} {copyResult.copied === 1 ? "file" : "files"} copied
              {copyResult.skipped > 0 && `, ${copyResult.skipped} skipped`}
            </div>
          </div>
        )}

        {phase === "error" && copyResult && (
          <div className="space-y-2 py-2">
            <div className="rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm dark:bg-red-950 dark:text-red-200 dark:border-red-800">
              {copyResult.errors.map((e, i) => <p key={i}>{e}</p>)}
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          {phase === "select" && (
            <>
              <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button size="sm" onClick={handleCopy} disabled={!destBucket}>Copy</Button>
            </>
          )}
          {(phase === "done" || phase === "error") && (
            <Button size="sm" onClick={() => onOpenChange(false)}>Close</Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
