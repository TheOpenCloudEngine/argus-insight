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
import { CsvViewer } from "./csv-viewer"
import { PdfViewer } from "./pdf-viewer"
import { VideoViewer } from "./video-viewer"
import { AudioViewer } from "./audio-viewer"
import { XlsxViewer } from "./xlsx-viewer"
import { DocxViewer } from "./docx-viewer"
import { ParquetViewer } from "./parquet-viewer"
import { PptxViewer } from "./pptx-viewer"

const MonacoEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.default), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[500px]">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  ),
})

/** Maximum file size in bytes that the text viewer can display (20 KB). */
const MAX_VIEW_SIZE = 20 * 1024

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

/** CSV/TSV extensions that use the dedicated table viewer. */
const csvExtensions: Record<string, string> = {
  csv: ",",
  tsv: "\t",
}

/** PDF extension. */
const pdfExtensions = new Set(["pdf"])

/** Video extensions. */
const videoExtensions = new Set(["mp4", "webm", "ogg", "mov", "m4v", "avi", "mkv"])

/** Audio extensions. */
const audioExtensions = new Set(["mp3", "wav", "m4a", "flac", "aac", "wma"])

/** Extensions handled by server-side preview API. */
const serverPreviewExtensions = new Set(["xls", "xlsx", "docx", "pptx", "parquet"])

/** File type category for routing to the correct viewer. */
type FileCategory =
  | "text"
  | "image"
  | "csv"
  | "pdf"
  | "video"
  | "audio"
  | "xlsx"
  | "docx"
  | "pptx"
  | "parquet"
  | null

function getFileCategory(ext: string): FileCategory {
  if (ext in extensionToLanguage) return "text"
  if (imageExtensions.has(ext)) return "image"
  if (ext in csvExtensions) return "csv"
  if (pdfExtensions.has(ext)) return "pdf"
  if (videoExtensions.has(ext)) return "video"
  if (audioExtensions.has(ext)) return "audio"
  if (ext === "xls" || ext === "xlsx") return "xlsx"
  if (ext === "docx") return "docx"
  if (ext === "pptx") return "pptx"
  if (ext === "parquet") return "parquet"
  return null
}

/** All viewable extensions. */
const viewableExtensions = new Set([
  ...Object.keys(extensionToLanguage),
  ...imageExtensions,
  ...Object.keys(csvExtensions),
  ...pdfExtensions,
  ...videoExtensions,
  ...audioExtensions,
  ...serverPreviewExtensions,
])

/** Check whether a file can be viewed. */
export function isViewableFile(name: string): boolean {
  return viewableExtensions.has(getExtension(name))
}

/** Check whether a file is CSV or TSV. */
export function isCsvTsvFile(name: string): boolean {
  return getExtension(name) in csvExtensions
}

/** Categories that skip the text-specific size limit. */
const SIZE_UNLIMITED_CATEGORIES = new Set<FileCategory>([
  "image", "csv", "pdf", "video", "audio", "xlsx", "docx", "pptx", "parquet",
])

/** Categories that need a wider dialog. */
const WIDE_DIALOG_CATEGORIES = new Set<FileCategory>([
  "csv", "xlsx", "parquet", "video", "pdf", "pptx",
])

type FileViewerDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  entry: StorageEntry | null
  /** Returns a presigned download URL for the given key. */
  getDownloadUrl: (key: string) => Promise<string>
  /** Server-side file preview (parquet, xlsx, xls, docx, pptx). */
  previewFile?: (
    key: string,
    options?: { sheet?: string; maxRows?: number },
  ) => Promise<unknown>
}

export function FileViewerDialog({
  open,
  onOpenChange,
  entry,
  getDownloadUrl,
  previewFile,
}: FileViewerDialogProps) {
  const [content, setContent] = useState<string | null>(null)
  const [mediaUrl, setMediaUrl] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<unknown>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = useCallback(() => {
    setContent(null)
    setMediaUrl(null)
    setPreviewData(null)
    setIsLoading(false)
    setError(null)
  }, [])

  useEffect(() => {
    if (!open || !entry || entry.kind === "folder") {
      reset()
      return
    }

    const ext = getExtension(entry.name)
    const category = getFileCategory(ext)

    if (!category) {
      setError("Unsupported file format.")
      return
    }

    // Size check for text files only
    if (!SIZE_UNLIMITED_CATEGORIES.has(category) && entry.size > MAX_VIEW_SIZE) {
      setError("Only files of 20 KB or smaller can be displayed.")
      return
    }

    setIsLoading(true)
    setError(null)

    // Server-side preview types
    if (serverPreviewExtensions.has(ext) && previewFile) {
      previewFile(entry.key)
        .then((data) => {
          setPreviewData(data)
          setIsLoading(false)
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : "Failed to load file")
          setIsLoading(false)
        })
      return
    }

    getDownloadUrl(entry.key)
      .then((url) => {
        if (category === "text") {
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
        // All other categories: pass URL to the dedicated viewer
        setMediaUrl(url)
        setIsLoading(false)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load file")
        setIsLoading(false)
      })
  }, [open, entry, getDownloadUrl, previewFile, reset])

  if (!entry) return null

  const ext = getExtension(entry.name)
  const category = getFileCategory(ext)
  const language = extensionToLanguage[ext] ?? "plaintext"
  const isWide = WIDE_DIALOG_CATEGORIES.has(category)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={`max-h-[85vh] flex flex-col ${isWide ? "sm:max-w-[1000px]" : "sm:max-w-[800px]"}`}>
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

          {/* Image */}
          {!isLoading && !error && category === "image" && mediaUrl && (
            <div className="flex items-center justify-center overflow-auto max-h-[70vh]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={mediaUrl}
                alt={entry.name}
                className="max-w-full max-h-[70vh] object-contain rounded"
              />
            </div>
          )}

          {/* CSV / TSV */}
          {!isLoading && !error && category === "csv" && mediaUrl && (
            <CsvViewer url={mediaUrl} defaultDelimiter={csvExtensions[ext]} />
          )}

          {/* PDF */}
          {!isLoading && !error && category === "pdf" && mediaUrl && (
            <PdfViewer url={mediaUrl} />
          )}

          {/* Video */}
          {!isLoading && !error && category === "video" && mediaUrl && (
            <VideoViewer url={mediaUrl} extension={ext} />
          )}

          {/* Audio */}
          {!isLoading && !error && category === "audio" && mediaUrl && (
            <AudioViewer url={mediaUrl} extension={ext} fileName={entry.name} />
          )}

          {/* XLSX / XLS (server-side preview) */}
          {!isLoading && !error && category === "xlsx" && previewData && (
            <XlsxViewer
              data={previewData as never}
              entryKey={entry.key}
              previewFile={previewFile}
            />
          )}

          {/* DOCX (server-side preview) */}
          {!isLoading && !error && category === "docx" && previewData && (
            <DocxViewer data={previewData as never} />
          )}

          {/* PPTX (server-side preview) */}
          {!isLoading && !error && category === "pptx" && previewData && (
            <PptxViewer data={previewData as never} />
          )}

          {/* Parquet (server-side preview) */}
          {!isLoading && !error && category === "parquet" && previewData && (
            <ParquetViewer data={previewData as never} />
          )}

          {/* Text / Code (Monaco) */}
          {!isLoading && !error && category === "text" && content !== null && (
            <div className="h-[500px] overflow-hidden">
              <MonacoEditor
                height="100%"
                language={language}
                value={content}
                theme="light"
                options={{
                  readOnly: true,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  fontSize: 13,
                  fontFamily: "D2Coding, monospace",
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
