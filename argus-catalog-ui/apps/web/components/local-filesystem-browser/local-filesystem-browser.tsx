"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Upload } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"

import type {
  FilesystemDataSource,
  FilesystemEntry,
  FilesystemFile,
  FilesystemFolder,
  SortConfig,
} from "./types"
import { BrowserBreadcrumb } from "./browser-breadcrumb"
import { BrowserToolbar } from "./browser-toolbar"
import { BrowserTable, type EntryContextAction } from "./browser-table"
import { CreateFolderDialog } from "./create-folder-dialog"
import { UploadDialog } from "./upload-dialog"
import { DeleteDialog } from "./delete-dialog"
import { PropertiesDialog } from "./properties-dialog"
import { RenameDialog } from "./rename-dialog"
import { UploadProgressDialog, type FileUploadStatus } from "./upload-progress-dialog"
import { FileViewerDialog, isViewableFile } from "./file-viewer-dialog"
import { CatViewerDialog } from "./cat-viewer-dialog"
import { entryId } from "./utils"

type LocalFilesystemBrowserProps = {
  /** Initial path to browse. Defaults to "/". */
  initialPath?: string
  /** Data source callbacks. */
  dataSource: FilesystemDataSource
  /** Optional CSS class for the root container. */
  className?: string
}

export function LocalFilesystemBrowser({
  initialPath = "/",
  dataSource,
  className,
}: LocalFilesystemBrowserProps) {
  // --- Navigation state ---
  const [currentPath, setCurrentPath] = useState(initialPath)
  const currentPathRef = useRef(currentPath)
  currentPathRef.current = currentPath
  const [navigationHistory, setNavigationHistory] = useState<string[]>([])

  // --- Data state ---
  const [folders, setFolders] = useState<FilesystemFolder[]>([])
  const [files, setFiles] = useState<FilesystemFile[]>([])
  const [isLoading, setIsLoading] = useState(false)

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
  const [propertiesEntry, setPropertiesEntry] = useState<FilesystemEntry | null>(null)
  const [propertiesOpen, setPropertiesOpen] = useState(false)

  // --- File viewer dialog state ---
  const [viewerEntry, setViewerEntry] = useState<FilesystemEntry | null>(null)
  const [viewerOpen, setViewerOpen] = useState(false)

  // --- Cat viewer dialog state ---
  const [catViewerEntry, setCatViewerEntry] = useState<FilesystemEntry | null>(null)
  const [catViewerOpen, setCatViewerOpen] = useState(false)

  // --- Context menu dialog state ---
  const [contextEntry, setContextEntry] = useState<FilesystemEntry | null>(null)
  const [renameOpen, setRenameOpen] = useState(false)
  const [contextDeleteOpen, setContextDeleteOpen] = useState(false)

  // --- Drag-and-drop state ---
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<FileUploadStatus[]>([])
  const [uploadProgressOpen, setUploadProgressOpen] = useState(false)
  const uploadNeedsRefresh = useRef(false)

  // --- Data fetching ---
  const fetchData = useCallback(
    async (targetPath: string) => {
      setIsLoading(true)
      try {
        const response = await dataSource.listDirectory(targetPath)
        setFolders(response.folders)
        setFiles(response.files)
      } finally {
        setIsLoading(false)
      }
    },
    [dataSource],
  )

  // Fetch on path change
  useEffect(() => {
    setSelectedKeys(new Set())
    setSearchValue("")
    fetchData(currentPath)
  }, [currentPath, fetchData])

  // --- Navigation ---
  function navigateTo(targetPath: string) {
    setNavigationHistory((prev) => [...prev, currentPath])
    setCurrentPath(targetPath)
  }

  // --- Sorting & filtering ---
  const entries = useMemo(() => {
    const all: FilesystemEntry[] = [...folders, ...files]

    // Filter
    const filtered = searchValue
      ? all.filter((e) =>
          e.name.toLowerCase().includes(searchValue.toLowerCase()),
        )
      : all

    // Sort: folders always first, then sort within each group
    const sortedFolders = filtered
      .filter((e): e is FilesystemFolder => e.kind === "folder")
      .sort((a, b) => {
        if (sort.column === "name") {
          const cmp = a.name.localeCompare(b.name)
          return sort.direction === "asc" ? cmp : -cmp
        }
        return 0
      })

    const sortedFiles = filtered
      .filter((e): e is FilesystemFile => e.kind === "file")
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

    return [...sortedFolders, ...sortedFiles]
  }, [folders, files, searchValue, sort])

  /** Find an entry by its entryId (kind:key). */
  function findEntryById(id: string): FilesystemEntry | undefined {
    return entries.find((e) => entryId(e.kind, e.key) === id)
  }

  /** Extract real paths from selectedKeys (entryId set). */
  function selectedRealPaths(): string[] {
    return Array.from(selectedKeys).map((id) => {
      const colonIdx = id.indexOf(":")
      return colonIdx >= 0 ? id.slice(colonIdx + 1) : id
    })
  }

  // --- Actions ---
  async function handleCreateFolder(folderName: string) {
    setDialogLoading(true)
    try {
      const newPath = currentPath.endsWith("/")
        ? `${currentPath}${folderName}`
        : `${currentPath}/${folderName}`
      await dataSource.createFolder(newPath)
      setCreateFolderOpen(false)
      await fetchData(currentPath)
    } finally {
      setDialogLoading(false)
    }
  }

  async function handleUpload(uploadedFiles: File[]) {
    setDialogLoading(true)
    try {
      await dataSource.uploadFiles(currentPath, uploadedFiles)
      setUploadOpen(false)
      await fetchData(currentPath)
    } finally {
      setDialogLoading(false)
    }
  }

  async function handleDelete() {
    setDialogLoading(true)
    try {
      await dataSource.deletePaths(selectedRealPaths())
      setDeleteOpen(false)
      setSelectedKeys(new Set())
      await fetchData(currentPath)
    } finally {
      setDialogLoading(false)
    }
  }

  async function downloadFile(path: string) {
    const url = await dataSource.getDownloadUrl(path)
    const response = await fetch(url)
    const blob = await response.blob()
    const octetBlob = new Blob([blob], { type: "application/octet-stream" })
    const blobUrl = URL.createObjectURL(octetBlob)
    const a = document.createElement("a")
    a.href = blobUrl
    a.download = path.split("/").filter(Boolean).pop() ?? "download"
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  }

  async function handleDownload() {
    const filePaths = selectedRealPaths().filter((k) => !k.endsWith("/"))
    for (const path of filePaths) {
      await downloadFile(path)
    }
  }

  // --- Double-click ---
  function handleEntryDoubleClick(entry: FilesystemEntry) {
    if (entry.kind === "folder") {
      navigateTo(entry.key)
      return
    }
    setPropertiesEntry(entry)
    setPropertiesOpen(true)
  }

  // --- Context menu actions ---
  function handleContextAction(action: EntryContextAction, entry: FilesystemEntry) {
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
        downloadFile(entry.key)
        break
    }
  }

  async function handleRename(newName: string) {
    if (!contextEntry || !dataSource.renamePath) return
    setDialogLoading(true)
    try {
      const oldPath = contextEntry.key
      const isFolder = contextEntry.kind === "folder"
      // Remove trailing slash for folder, then get parent
      const cleanPath = isFolder ? oldPath.slice(0, -1) : oldPath
      const parentDir = cleanPath.substring(0, cleanPath.lastIndexOf("/") + 1)
      const newPath = parentDir + newName + (isFolder ? "/" : "")

      await dataSource.renamePath(oldPath.replace(/\/$/, ""), newPath.replace(/\/$/, ""))
      setRenameOpen(false)
      await fetchData(currentPathRef.current)
    } finally {
      setDialogLoading(false)
    }
  }

  async function handleContextDelete() {
    setDialogLoading(true)
    try {
      await dataSource.deletePaths(selectedRealPaths())
      setContextDeleteOpen(false)
      setSelectedKeys(new Set())
      await fetchData(currentPathRef.current)
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

    const uploadDir = currentPathRef.current

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
      setUploadProgress((prev) =>
        prev.map((item, idx) =>
          idx === i ? { ...item, status: "uploading" } : item,
        ),
      )

      try {
        if (uploadFn) {
          await uploadFn(uploadDir, droppedFiles[i], (progress) => {
            setUploadProgress((prev) =>
              prev.map((item, idx) =>
                idx === i ? { ...item, progress } : item,
              ),
            )
          })
        } else {
          await dataSource.uploadFiles(uploadDir, [droppedFiles[i]])
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
      fetchData(currentPathRef.current)
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
          currentPath={currentPath}
          onNavigate={(p) => {
            setNavigationHistory([])
            setCurrentPath(p)
          }}
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
          onRefresh={() => fetchData(currentPath)}
          isLoading={isLoading}
        />

        {/* Table */}
        <BrowserTable
          entries={entries}
          totalEntryCount={folders.length + files.length}
          selectedKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
          onFolderOpen={navigateTo}
          onEntryDoubleClick={handleEntryDoubleClick}
          onContextAction={handleContextAction}
          sort={sort}
          onSortChange={setSort}
          isLoading={isLoading}
        />

        {/* Status bar */}
        <div className="flex items-center justify-between text-sm text-muted-foreground px-1">
          <span>
            {folders.length} folder{folders.length !== 1 ? "s" : ""},{" "}
            {files.length} file{files.length !== 1 ? "s" : ""}
            {searchValue && ` (filtered: ${entries.length})`}
          </span>
        </div>
      </div>

      {/* Dialogs */}
      <CreateFolderDialog
        open={createFolderOpen}
        onOpenChange={setCreateFolderOpen}
        currentPath={currentPath}
        onConfirm={handleCreateFolder}
        isLoading={dialogLoading}
      />
      <UploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        currentPath={currentPath}
        onConfirm={handleUpload}
        isLoading={dialogLoading}
      />
      <DeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        selectedPaths={selectedRealPaths()}
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
        selectedPaths={contextEntry ? [contextEntry.key] : []}
        onConfirm={handleContextDelete}
        isLoading={dialogLoading}
      />
      <FileViewerDialog
        open={viewerOpen}
        onOpenChange={setViewerOpen}
        entry={viewerEntry}
        getDownloadUrl={(path) => dataSource.getDownloadUrl(path)}
        previewFile={
          dataSource.previewFile
            ? (path, options) => dataSource.previewFile!(path, options)
            : undefined
        }
      />
      <CatViewerDialog
        open={catViewerOpen}
        onOpenChange={setCatViewerOpen}
        entry={catViewerEntry}
        getDownloadUrl={(path) => dataSource.getDownloadUrl(path)}
      />
    </div>
  )
}
