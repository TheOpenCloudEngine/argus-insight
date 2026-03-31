"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Loader2, Upload } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"
import { Button } from "@workspace/ui/components/button"

import type {
  BrowserDataSource,
  FilebrowserConfig,
  SortConfig,
  StorageEntry,
  StorageFolder,
  StorageObject,
} from "./types"
import { BrowserBreadcrumb } from "./browser-breadcrumb"
import { BrowserToolbar } from "./browser-toolbar"
import { BrowserTable, type EntryContextAction } from "./browser-table"
import { CreateFolderDialog } from "./create-folder-dialog"
import { UploadDialog } from "./upload-dialog"
import { DeleteDialog } from "./delete-dialog"
import { PropertiesDialog } from "./properties-dialog"
import { RenameDialog } from "./rename-dialog"
import { CopyToDialog } from "./copy-to-dialog"
import { UploadProgressDialog, type FileUploadStatus } from "./upload-progress-dialog"
import { FileViewerDialog, isViewableFile } from "./file-viewer-dialog"
import { CatViewerDialog } from "./cat-viewer-dialog"
import { entryId } from "./utils"

type ObjectStorageBrowserProps = {
  /** The bucket name to browse. */
  bucket: string
  /** Data source callbacks. */
  dataSource: BrowserDataSource
  /** Optional CSS class for the root container. */
  className?: string
  /** Available bucket names for the combo box selector. */
  buckets?: string[]
  /** Callback when user selects a different bucket. */
  onBucketChange?: (bucket: string) => void
}

export function ObjectStorageBrowser({
  bucket,
  dataSource,
  className,
  buckets,
  onBucketChange,
}: ObjectStorageBrowserProps) {
  // --- Navigation state ---
  const [prefix, setPrefix] = useState("")
  const prefixRef = useRef(prefix)
  prefixRef.current = prefix
  const [navigationHistory, setNavigationHistory] = useState<string[]>([])

  // --- Data state ---
  const [folders, setFolders] = useState<StorageFolder[]>([])
  const [objects, setObjects] = useState<StorageObject[]>([])
  const [continuationToken, setContinuationToken] = useState<string | undefined>()
  const [isTruncated, setIsTruncated] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  // --- UI state ---
  const [searchValue, setSearchValue] = useState("")
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())
  const [sort, setSort] = useState<SortConfig>({ column: "name", direction: "asc" })

  // --- Dialog state ---
  const [createFolderOpen, setCreateFolderOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [dialogLoading, setDialogLoading] = useState(false)

  // --- Properties dialog state ---
  const [propertiesEntry, setPropertiesEntry] = useState<StorageEntry | null>(null)
  const [propertiesOpen, setPropertiesOpen] = useState(false)

  // --- File viewer dialog state ---
  const [viewerEntry, setViewerEntry] = useState<StorageEntry | null>(null)
  const [viewerOpen, setViewerOpen] = useState(false)

  // --- Cat viewer dialog state ---
  const [catViewerEntry, setCatViewerEntry] = useState<StorageEntry | null>(null)
  const [catViewerOpen, setCatViewerOpen] = useState(false)

  // --- Context menu dialog state ---
  const [contextEntry, setContextEntry] = useState<StorageEntry | null>(null)
  const [renameOpen, setRenameOpen] = useState(false)
  const [copyToOpen, setCopyToOpen] = useState(false)
const [contextDeleteOpen, setContextDeleteOpen] = useState(false)

  // --- Drag-and-drop state ---
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<FileUploadStatus[]>([])
  const [uploadProgressOpen, setUploadProgressOpen] = useState(false)
  const uploadNeedsRefresh = useRef(false)

  // --- File Browser configuration ---
  const [fbConfig, setFbConfig] = useState<FilebrowserConfig | null>(null)

  useEffect(() => {
    if (dataSource.fetchConfiguration) {
      dataSource.fetchConfiguration()
        .then((config) => {
          console.log("[FileBrowser] Configuration loaded:", config)
          setFbConfig(config)
        })
        .catch((err) => {
          console.error("Failed to fetch filebrowser config:", err)
        })
    }
  }, [dataSource])

  // --- Data fetching ---
  const fetchData = useCallback(
    async (targetPrefix: string, token?: string) => {
      const isAppend = !!token
      if (isAppend) {
        setIsLoadingMore(true)
      } else {
        setIsLoading(true)
      }

      try {
        const response = await dataSource.listObjects(bucket, targetPrefix, token)

        if (isAppend) {
          setObjects((prev) => [...prev, ...response.objects])
        } else {
          setFolders(response.folders)
          setObjects(response.objects)
        }
        setContinuationToken(response.nextContinuationToken)
        setIsTruncated(response.isTruncated)
      } finally {
        setIsLoading(false)
        setIsLoadingMore(false)
      }
    },
    [bucket, dataSource],
  )

  // Fetch on prefix change
  useEffect(() => {
    setSelectedKeys(new Set())
    setSearchValue("")
    setContinuationToken(undefined)
    fetchData(prefix)
  }, [prefix, fetchData])

  // --- Navigation ---
  function navigateTo(targetPrefix: string) {
    setNavigationHistory((prev) => [...prev, prefix])
    setPrefix(targetPrefix)
  }

  function navigateBack() {
    const prev = navigationHistory[navigationHistory.length - 1]
    if (prev !== undefined) {
      setNavigationHistory((h) => h.slice(0, -1))
      setPrefix(prev)
    }
  }

  // --- Sorting & filtering ---
  const entries = useMemo(() => {
    const all: StorageEntry[] = [...folders, ...objects]

    // Filter
    const filtered = searchValue
      ? all.filter((e) =>
          e.name.toLowerCase().includes(searchValue.toLowerCase()),
        )
      : all

    // Skip sorting when directory has >= threshold entries for performance
    const sortThreshold = fbConfig?.browser?.sort_disable_threshold ?? 300
    if (all.length >= sortThreshold) {
      const unsortedFolders = filtered.filter((e): e is StorageFolder => e.kind === "folder")
      const unsortedObjects = filtered.filter((e): e is StorageObject => e.kind === "object")
      return [...unsortedFolders, ...unsortedObjects]
    }

    // Sort: folders always first, then sort within each group
    const sortedFolders = filtered
      .filter((e): e is StorageFolder => e.kind === "folder")
      .sort((a, b) => {
        if (sort.column === "name") {
          const cmp = a.name.localeCompare(b.name)
          return sort.direction === "asc" ? cmp : -cmp
        }
        return 0
      })

    const sortedObjects = filtered
      .filter((e): e is StorageObject => e.kind === "object")
      .sort((a, b) => {
        let cmp = 0
        switch (sort.column) {
          case "name":
            cmp = a.name.localeCompare(b.name)
            break
          case "size":
            cmp = a.size - b.size
            break
          case "lastModified":
            cmp = new Date(a.lastModified).getTime() - new Date(b.lastModified).getTime()
            break
        }
        return sort.direction === "asc" ? cmp : -cmp
      })

    return [...sortedFolders, ...sortedObjects]
  }, [folders, objects, searchValue, sort])

  /** Find an entry by its entryId (kind:key). */
  function findEntryById(id: string): StorageEntry | undefined {
    return entries.find((e) => entryId(e.kind, e.key) === id)
  }

  /** Extract real S3 keys from selectedKeys (entryId set). */
  function selectedRealKeys(): string[] {
    return Array.from(selectedKeys).map((id) => {
      const colonIdx = id.indexOf(":")
      return colonIdx >= 0 ? id.slice(colonIdx + 1) : id
    })
  }

  // --- Actions ---
  async function handleCreateFolder(folderName: string) {
    setDialogLoading(true)
    try {
      await dataSource.createFolder(bucket, `${prefix}${folderName}/`)
      setCreateFolderOpen(false)
      await fetchData(prefix)
    } finally {
      setDialogLoading(false)
    }
  }

  async function handleUpload(files: File[]) {
    setDialogLoading(true)
    try {
      await dataSource.uploadFiles(bucket, prefix, files)
      setUploadOpen(false)
      await fetchData(prefix)
    } finally {
      setDialogLoading(false)
    }
  }

  async function handleDelete() {
    setDialogLoading(true)
    try {
      await dataSource.deleteObjects(bucket, selectedRealKeys())
      setDeleteOpen(false)
      setSelectedKeys(new Set())
      await fetchData(prefix)
    } finally {
      setDialogLoading(false)
    }
  }

  async function downloadAsOctetStream(key: string) {
    const url = await dataSource.getDownloadUrl(bucket, key)
    const response = await fetch(url)
    const blob = await response.blob()
    const octetBlob = new Blob([blob], { type: "application/octet-stream" })
    const blobUrl = URL.createObjectURL(octetBlob)
    const a = document.createElement("a")
    a.href = blobUrl
    a.download = key.split("/").filter(Boolean).pop() ?? "download"
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  }

  async function handleDownload() {
    const fileKeys = selectedRealKeys().filter((k) => !k.endsWith("/"))
    for (const key of fileKeys) {
      await downloadAsOctetStream(key)
    }
  }

  function handleLoadMore() {
    if (continuationToken) {
      fetchData(prefix, continuationToken)
    }
  }

  // --- Double-click properties ---
  function handleEntryDoubleClick(entry: StorageEntry) {
    // For folders, double-click navigates into them
    if (entry.kind === "folder") {
      navigateTo(entry.key)
      return
    }
    // For files, show properties
    setPropertiesEntry(entry)
    setPropertiesOpen(true)
  }

  // --- Context menu actions ---
  function handleContextAction(action: EntryContextAction, entry: StorageEntry) {
    setContextEntry(entry)
    switch (action) {
      case "rename":
        setRenameOpen(true)
        break
      case "delete":
        setSelectedKeys(new Set([entryId(entry.kind, entry.key)]))
        setContextDeleteOpen(true)
        break
case "properties":
        setPropertiesEntry(entry)
        setPropertiesOpen(true)
        break
      case "view":
        setViewerEntry(entry)
        setViewerOpen(true)
        break
      case "view-cat":
        setCatViewerEntry(entry)
        setCatViewerOpen(true)
        break
      case "download":
        downloadAsOctetStream(entry.key)
        break
    }
  }

  async function handleRename(newName: string) {
    if (!contextEntry || !dataSource.copyObject) return
    setDialogLoading(true)
    try {
      // Build new key: same parent prefix + new name
      const oldKey = contextEntry.key
      const isFolder = contextEntry.kind === "folder"
      const parentPrefix = oldKey.substring(0, oldKey.lastIndexOf("/", isFolder ? oldKey.length - 2 : oldKey.length) + 1)
      const newKey = parentPrefix + newName + (isFolder ? "/" : "")

      await dataSource.copyObject(bucket, oldKey, newKey)
      await dataSource.deleteObjects(bucket, [oldKey])
      setRenameOpen(false)
      await fetchData(prefixRef.current)
    } finally {
      setDialogLoading(false)
    }
  }

async function handleContextDelete() {
    setDialogLoading(true)
    try {
      await dataSource.deleteObjects(bucket, selectedRealKeys())
      setContextDeleteOpen(false)
      setSelectedKeys(new Set())
      await fetchData(prefixRef.current)
    } finally {
      setDialogLoading(false)
    }
  }

  // --- Drag-and-drop upload with progress ---
  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    // Only set false if leaving the container (not entering a child)
    if (e.currentTarget === e.target || !e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false)
    }
  }

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)

    const droppedFiles = Array.from(e.dataTransfer.files)
    if (droppedFiles.length === 0) return

    // Capture current prefix for upload paths
    const uploadPrefix = prefixRef.current

    // Initialize progress tracking
    const initialStatus: FileUploadStatus[] = droppedFiles.map((file) => ({
      file,
      progress: 0,
      status: "pending",
    }))
    setUploadProgress(initialStatus)
    setUploadProgressOpen(true)
    uploadNeedsRefresh.current = true

    const uploadFn = dataSource.uploadFileWithProgress

    for (let i = 0; i < droppedFiles.length; i++) {
      // Mark current file as uploading
      setUploadProgress((prev) =>
        prev.map((item, idx) =>
          idx === i ? { ...item, status: "uploading" } : item,
        ),
      )

      try {
        if (uploadFn) {
          await uploadFn(bucket, uploadPrefix, droppedFiles[i], (progress) => {
            setUploadProgress((prev) =>
              prev.map((item, idx) =>
                idx === i ? { ...item, progress } : item,
              ),
            )
          })
        } else {
          // Fallback: upload without granular progress
          await dataSource.uploadFiles(bucket, uploadPrefix, [droppedFiles[i]])
        }

        setUploadProgress((prev) =>
          prev.map((item, idx) =>
            idx === i ? { ...item, progress: 100, status: "done" } : item,
          ),
        )
      } catch (err) {
        setUploadProgress((prev) =>
          prev.map((item, idx) =>
            idx === i
              ? {
                  ...item,
                  status: "error",
                  error: err instanceof Error ? err.message : "Upload failed",
                }
              : item,
          ),
        )
      }
    }
  }

  function handleUploadProgressClose(open: boolean) {
    setUploadProgressOpen(open)
    if (!open && uploadNeedsRefresh.current) {
      uploadNeedsRefresh.current = false
      fetchData(prefixRef.current)
    }
  }

  return (
    <div
      className={cn("relative", className)}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drag overlay */}
      {isDragOver && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm border-2 border-dashed border-primary rounded-lg">
          <div className="flex flex-col items-center gap-3 text-primary">
            <Upload className="h-12 w-12" />
            <p className="text-lg font-medium">Drop files to upload</p>
            <p className="text-sm text-muted-foreground">
              Files will be uploaded to the current directory
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {/* Breadcrumb */}
        <BrowserBreadcrumb
          bucket={bucket}
          prefix={prefix}
          onNavigate={(p) => {
            setNavigationHistory([])
            setPrefix(p)
          }}
          buckets={buckets}
          onBucketChange={onBucketChange}
        />

        {/* Toolbar */}
        <BrowserToolbar
          searchValue={searchValue}
          onSearchChange={setSearchValue}
          selectedCount={selectedKeys.size}
          onUpload={() => setUploadOpen(true)}
          onCreateFolder={() => setCreateFolderOpen(true)}
          onDelete={() => setDeleteOpen(true)}
          onDownload={handleDownload}
          onRename={() => {
            const id = Array.from(selectedKeys)[0]
            const entry = findEntryById(id)
            if (entry) {
              setContextEntry(entry)
              setRenameOpen(true)
            }
          }}
          onCopyTo={() => setCopyToOpen(true)}
          onProperties={() => {
            const id = Array.from(selectedKeys)[0]
            const entry = findEntryById(id)
            if (entry) {
              setPropertiesEntry(entry)
              setPropertiesOpen(true)
            }
          }}
          onView={() => {
            const id = Array.from(selectedKeys)[0]
            const entry = findEntryById(id)
            if (entry) {
              setViewerEntry(entry)
              setViewerOpen(true)
            }
          }}
          viewDisabled={(() => {
            if (selectedKeys.size !== 1) return true
            const id = Array.from(selectedKeys)[0]
            const entry = findEntryById(id)
            return !entry || entry.kind === "folder" || !isViewableFile(entry.name)
          })()}
          onRefresh={() => fetchData(prefix)}
          isLoading={isLoading}
        />

        {/* Table */}
        <BrowserTable
          entries={entries}
          totalEntryCount={folders.length + objects.length}
          selectedKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
          onFolderOpen={navigateTo}
          onEntryDoubleClick={handleEntryDoubleClick}
          onContextAction={handleContextAction}
          sort={sort}
          onSortChange={setSort}
          isLoading={isLoading}
          sortDisableThreshold={fbConfig?.browser?.sort_disable_threshold ?? 300}
        />

        {/* Load more / status bar */}
        <div className="flex items-center justify-between text-sm text-muted-foreground px-1">
          <span>
            {folders.length} folder{folders.length !== 1 ? "s" : ""},{" "}
            {objects.length} object{objects.length !== 1 ? "s" : ""}
            {searchValue && ` (filtered: ${entries.length})`}
          </span>
          {isTruncated && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleLoadMore}
              disabled={isLoadingMore}
              className="h-7 text-xs"
            >
              {isLoadingMore ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin mr-1.5" />
                  Loading...
                </>
              ) : (
                "Load more"
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <CreateFolderDialog
        open={createFolderOpen}
        onOpenChange={setCreateFolderOpen}
        currentPrefix={prefix}
        onConfirm={handleCreateFolder}
        isLoading={dialogLoading}
      />
      <UploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        currentPrefix={prefix}
        onConfirm={handleUpload}
        isLoading={dialogLoading}
      />
      <DeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        selectedKeys={selectedRealKeys()}
        onConfirm={handleDelete}
        isLoading={dialogLoading}
      />
      <PropertiesDialog
        open={propertiesOpen}
        onOpenChange={setPropertiesOpen}
        entry={propertiesEntry}
      />
      <UploadProgressDialog
        open={uploadProgressOpen}
        onOpenChange={handleUploadProgressClose}
        items={uploadProgress}
      />
      <RenameDialog
        open={renameOpen}
        onOpenChange={setRenameOpen}
        currentName={contextEntry?.name ?? ""}
        onConfirm={handleRename}
        isLoading={dialogLoading}
      />
<DeleteDialog
        open={contextDeleteOpen}
        onOpenChange={setContextDeleteOpen}
        selectedKeys={contextEntry ? [contextEntry.key] : []}
        onConfirm={handleContextDelete}
        isLoading={dialogLoading}
      />
      <FileViewerDialog
        open={viewerOpen}
        onOpenChange={setViewerOpen}
        entry={viewerEntry}
        getDownloadUrl={(key) => dataSource.getDownloadUrl(bucket, key)}
        previewFile={
          dataSource.previewFile
            ? (key, options) => dataSource.previewFile!(bucket, key, options)
            : undefined
        }
        config={fbConfig}
      />
      <CatViewerDialog
        open={catViewerOpen}
        onOpenChange={setCatViewerOpen}
        entry={catViewerEntry}
        getDownloadUrl={(key) => dataSource.getDownloadUrl(bucket, key)}
      />
      <CopyToDialog
        open={copyToOpen}
        onOpenChange={setCopyToOpen}
        sourceBucket={bucket}
        sourceKeys={selectedRealKeys()}
        onComplete={() => fetchData(prefix)}
      />
    </div>
  )
}
