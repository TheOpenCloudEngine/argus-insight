"use client"

import { useCallback, useEffect, useState } from "react"
import dynamic from "next/dynamic"
import { Loader2 } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"

import type { StorageEntry } from "./types"
import { getExtension } from "./utils"

const MonacoEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.default), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[500px]">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  ),
})

/** Maximum file size in bytes that the viewer can display (10 KB). */
const MAX_VIEW_SIZE = 10 * 1024

/** Map file extensions to Monaco Editor language identifiers. */
const extensionToLanguage: Record<string, string> = {
  // Python
  py: "python",
  // Java
  java: "java",
  // Notebook (treated as JSON)
  ipynb: "json",
  // C/C++
  c: "c",
  cpp: "cpp",
  h: "c",
  hpp: "cpp",
  // Web
  html: "html",
  htm: "html",
  css: "css",
  js: "javascript",
  ts: "typescript",
  // Go
  go: "go",
  // Rust
  rs: "rust",
  // Shell
  sh: "shell",
  bash: "shell",
  zsh: "shell",
  // JSON
  json: "json",
  // YAML
  yaml: "yaml",
  yml: "yaml",
  // XML
  xml: "xml",
  // INI/CONF
  ini: "ini",
  conf: "ini",
  config: "ini",
  // Markdown
  md: "markdown",
  // Log
  log: "plaintext",
  // Environment
  env: "plaintext",
  // Plain text
  txt: "plaintext",
}

/** Image extensions that should be rendered as an image preview. */
const imageExtensions = new Set([
  "jpg", "jpeg", "png", "gif", "svg", "webp", "bmp", "ico", "tiff",
])

/** All viewable extensions (code/text + images). */
const viewableExtensions = new Set([
  ...Object.keys(extensionToLanguage),
  ...imageExtensions,
])

/** Check whether a file can be viewed. */
export function isViewableFile(name: string): boolean {
  return viewableExtensions.has(getExtension(name))
}

type FileViewerDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  entry: StorageEntry | null
  /** Returns a presigned download URL for the given key. */
  getDownloadUrl: (key: string) => Promise<string>
}

export function FileViewerDialog({
  open,
  onOpenChange,
  entry,
  getDownloadUrl,
}: FileViewerDialogProps) {
  const [content, setContent] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = useCallback(() => {
    setContent(null)
    setImageUrl(null)
    setIsLoading(false)
    setError(null)
  }, [])

  useEffect(() => {
    if (!open || !entry || entry.kind === "folder") {
      reset()
      return
    }

    const ext = getExtension(entry.name)
    const isImage = imageExtensions.has(ext)

    // Size check for non-image files
    if (!isImage && entry.size > MAX_VIEW_SIZE) {
      setError("Only files of 10 KB or smaller can be displayed.")
      return
    }

    setIsLoading(true)
    setError(null)

    getDownloadUrl(entry.key)
      .then((url) => {
        if (isImage) {
          setImageUrl(url)
          setIsLoading(false)
        } else {
          return fetch(url)
            .then((res) => {
              if (!res.ok) throw new Error(`Failed to fetch file (${res.status})`)
              return res.text()
            })
            .then((text) => {
              setContent(text)
              setIsLoading(false)
            })
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load file")
        setIsLoading(false)
      })
  }, [open, entry, getDownloadUrl, reset])

  if (!entry) return null

  const ext = getExtension(entry.name)
  const isImage = imageExtensions.has(ext)
  const language = extensionToLanguage[ext] ?? "plaintext"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="truncate">{entry.name}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 min-h-0 mt-2">
          {isLoading && (
            <div className="flex items-center justify-center h-[500px]">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center h-[200px]">
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
          )}

          {!isLoading && !error && isImage && imageUrl && (
            <div className="flex items-center justify-center overflow-auto max-h-[70vh]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt={entry.name}
                className="max-w-full max-h-[70vh] object-contain rounded"
              />
            </div>
          )}

          {!isLoading && !error && !isImage && content !== null && (
            <div className="h-[500px] border rounded overflow-hidden">
              <MonacoEditor
                height="100%"
                language={language}
                value={content}
                theme="vs-dark"
                options={{
                  readOnly: true,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  fontSize: 13,
                  lineNumbers: "on",
                  wordWrap: "on",
                  domReadOnly: true,
                }}
              />
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
