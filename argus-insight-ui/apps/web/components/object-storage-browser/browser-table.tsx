"use client"

import { useCallback, useEffect, useState } from "react"
import { createPortal } from "react-dom"
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ClipboardCopy,
  File,
  FileArchive,
  FileAudio,
  FileCode,
  FileImage,
  FileText,
  FileVideo,
  Folder,
  FileSpreadsheet,
  FileType,
  Eye,
  Pencil,
  Trash2,
  FolderInput,
  Info,
  Download,
} from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"
import { Checkbox } from "@workspace/ui/components/checkbox"
import {
  ContextMenu,
  ContextMenuTrigger,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
} from "@workspace/ui/components/context-menu"

import type { StorageEntry, SortConfig, SortDirection } from "./types"
import { entryId, formatBytes, formatDate, getFileCategory } from "./utils"
import { isViewableFile } from "./file-viewer-dialog"

export type EntryContextAction = "rename" | "delete" | "move" | "properties" | "view" | "download"

type BrowserTableProps = {
  entries: StorageEntry[]
  /**
   * Total number of entries (folders + objects) before filtering.
   * Used to disable sorting when >= 300 items for performance.
   */
  totalEntryCount: number
  selectedKeys: Set<string>
  onSelectionChange: (keys: Set<string>) => void
  onFolderOpen: (prefix: string) => void
  onEntryDoubleClick?: (entry: StorageEntry) => void
  onContextAction?: (action: EntryContextAction, entry: StorageEntry) => void
  sort: SortConfig
  onSortChange: (sort: SortConfig) => void
  isLoading: boolean
}

/**
 * Sorting is disabled when the directory has 300 or more entries (folders + objects)
 * to prevent performance issues with large directories.
 */
const SORT_DISABLE_THRESHOLD = 300

const fileIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  image: FileImage,
  video: FileVideo,
  audio: FileAudio,
  archive: FileArchive,
  code: FileCode,
  document: FileText,
  text: FileType,
  data: FileSpreadsheet,
  generic: File,
}

function FileIcon({ name, className }: { name: string; className?: string }) {
  const category = getFileCategory(name)
  const Icon = fileIcons[category] ?? File
  return <Icon className={className} />
}

function SortButton({
  column,
  label,
  currentSort,
  onSortChange,
  disabled,
  className,
}: {
  column: SortConfig["column"]
  label: string
  currentSort: SortConfig
  onSortChange: (sort: SortConfig) => void
  disabled?: boolean
  className?: string
}) {
  const isActive = !disabled && currentSort.column === column
  const nextDirection: SortDirection =
    isActive && currentSort.direction === "asc" ? "desc" : "asc"

  return (
    <button
      type="button"
      onClick={() => !disabled && onSortChange({ column, direction: nextDirection })}
      disabled={disabled}
      className={cn(
        "flex items-center gap-1 transition-colors",
        disabled
          ? "text-muted-foreground cursor-default"
          : "hover:text-foreground",
        !disabled && isActive ? "text-foreground" : "text-muted-foreground",
        className,
      )}
    >
      {label}
      {disabled ? null : isActive ? (
        currentSort.direction === "asc" ? (
          <ArrowUp className="h-3.5 w-3.5" />
        ) : (
          <ArrowDown className="h-3.5 w-3.5" />
        )
      ) : (
        <ArrowUpDown className="h-3.5 w-3.5" />
      )}
    </button>
  )
}

function CopyToast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 2000)
    return () => clearTimeout(timer)
  }, [onDone])

  return createPortal(
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[9999] animate-in fade-in slide-in-from-bottom-2 duration-200">
      <div className="bg-foreground text-background text-sm px-4 py-2 rounded-md shadow-lg">
        {message}
      </div>
    </div>,
    document.body,
  )
}

function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(text)
  }
  // Fallback for non-secure contexts
  const textarea = document.createElement("textarea")
  textarea.value = text
  textarea.style.position = "fixed"
  textarea.style.opacity = "0"
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand("copy")
  document.body.removeChild(textarea)
  return Promise.resolve()
}

export function BrowserTable({
  entries,
  totalEntryCount,
  selectedKeys,
  onSelectionChange,
  onFolderOpen,
  onEntryDoubleClick,
  onContextAction,
  sort,
  onSortChange,
  isLoading,
}: BrowserTableProps) {
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const hideToast = useCallback(() => setToastMessage(null), [])

  async function handleCopyPath(entry: StorageEntry) {
    try {
      await copyToClipboard(entry.key)
      setToastMessage("Copied to clipboard. (May not work without HTTPS)")
    } catch {
      setToastMessage("Failed to copy.")
    }
  }

  // Disable sorting when the directory has >= 300 entries for performance
  const sortDisabled = totalEntryCount >= SORT_DISABLE_THRESHOLD
  const allSelectableKeys = entries.map((e) => entryId(e.kind, e.key))
  const allSelected =
    allSelectableKeys.length > 0 &&
    allSelectableKeys.every((k) => selectedKeys.has(k))
  const someSelected =
    !allSelected && allSelectableKeys.some((k) => selectedKeys.has(k))

  function toggleAll() {
    if (allSelected) {
      onSelectionChange(new Set())
    } else {
      onSelectionChange(new Set(allSelectableKeys))
    }
  }

  function toggleOne(key: string) {
    const next = new Set(selectedKeys)
    if (next.has(key)) {
      next.delete(key)
    } else {
      next.add(key)
    }
    onSelectionChange(next)
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
          <span className="text-sm">Loading...</span>
        </div>
      </div>
    )
  }

  if (entries.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Folder className="h-12 w-12 opacity-30" />
          <span className="text-sm">This folder is empty</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-auto border rounded-md">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm border-b">
          <tr>
            <th className="w-10 px-3 py-2">
              <Checkbox
                checked={allSelected ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={toggleAll}
                aria-label="Select all"
              />
            </th>
            <th className="text-left px-3 py-2 font-medium">
              <SortButton
                column="name"
                label="Name"
                currentSort={sort}
                onSortChange={onSortChange}
                disabled={sortDisabled}
              />
            </th>
            <th className="text-right px-3 py-2 font-medium w-28">
              <SortButton
                column="size"
                label="Size"
                currentSort={sort}
                onSortChange={onSortChange}
                disabled={sortDisabled}
                className="justify-end"
              />
            </th>
            <th className="text-left px-3 py-2 font-medium w-48">
              <SortButton
                column="lastModified"
                label="Last Modified"
                currentSort={sort}
                onSortChange={onSortChange}
                disabled={sortDisabled}
              />
            </th>
            <th className="text-left px-3 py-2 font-medium w-32">
              Storage Class
            </th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {entries.map((entry) => {
            const isFolder = entry.kind === "folder"
            const id = entryId(entry.kind, entry.key)
            const isSelected = selectedKeys.has(id)

            return (
              <ContextMenu key={id}>
                <ContextMenuTrigger asChild>
                  <tr
                    onDoubleClick={() => onEntryDoubleClick?.(entry)}
                    className={cn(
                      "hover:bg-muted/50 transition-colors cursor-pointer",
                      isSelected && "bg-muted/40",
                    )}
                  >
                    <td className="px-3 py-1.5">
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => toggleOne(id)}
                        aria-label={`Select ${entry.name}`}
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      {isFolder ? (
                        <button
                          type="button"
                          onClick={() => onFolderOpen(entry.key)}
                          className="flex items-center gap-2 hover:text-primary transition-colors group"
                        >
                          <Folder className="h-4 w-4 text-muted-foreground shrink-0" />
                          <span className="group-hover:underline truncate">
                            {entry.name}
                          </span>
                        </button>
                      ) : (
                        <div className="flex items-center gap-2">
                          <FileIcon
                            name={entry.name}
                            className="h-4 w-4 text-muted-foreground shrink-0"
                          />
                          <span className="truncate">{entry.name}</span>
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right text-muted-foreground tabular-nums">
                      {isFolder ? "-" : formatBytes(entry.size)}
                    </td>
                    <td className="px-3 py-1.5 text-muted-foreground">
                      {isFolder ? "-" : formatDate(entry.lastModified)}
                    </td>
                    <td className="px-3 py-1.5 text-muted-foreground">
                      {isFolder ? "-" : (entry.storageClass ?? "STANDARD")}
                    </td>
                  </tr>
                </ContextMenuTrigger>
                <ContextMenuContent>
                  <ContextMenuItem onClick={() => onContextAction?.("rename", entry)}>
                    <Pencil className="h-4 w-4" />
                    Rename
                  </ContextMenuItem>
                  <ContextMenuItem onClick={() => onContextAction?.("delete", entry)}>
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </ContextMenuItem>
                  <ContextMenuItem onClick={() => onContextAction?.("move", entry)}>
                    <FolderInput className="h-4 w-4" />
                    Move
                  </ContextMenuItem>
                  <ContextMenuSeparator />
                  <ContextMenuItem onClick={() => onContextAction?.("properties", entry)}>
                    <Info className="h-4 w-4" />
                    Properties
                  </ContextMenuItem>
                  {entry.kind === "object" && (
                    <ContextMenuItem
                      onClick={() => onContextAction?.("view", entry)}
                      disabled={!isViewableFile(entry.name)}
                    >
                      <Eye className="h-4 w-4" />
                      View
                    </ContextMenuItem>
                  )}
                  {entry.kind === "object" && (
                    <>
                      <ContextMenuSeparator />
                      <ContextMenuItem onClick={() => onContextAction?.("download", entry)}>
                        <Download className="h-4 w-4" />
                        Download
                      </ContextMenuItem>
                    </>
                  )}
                  <ContextMenuSeparator />
                  <ContextMenuItem onClick={() => handleCopyPath(entry)}>
                    <ClipboardCopy className="h-4 w-4" />
                    Copy Path
                  </ContextMenuItem>
                </ContextMenuContent>
              </ContextMenu>
            )
          })}
        </tbody>
      </table>
      {toastMessage && <CopyToast message={toastMessage} onDone={hideToast} />}
    </div>
  )
}
