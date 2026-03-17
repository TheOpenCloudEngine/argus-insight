"use client"

import { useCallback, useEffect, useState } from "react"
import {
  Eye,
  Columns2,
  Pencil,
  Save,
  History,
  FileText,
} from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Separator } from "@workspace/ui/components/separator"
import Editor, { type Monaco } from "@monaco-editor/react"
import { MarkdownPreview } from "./markdown-preview"
import { VersionHistory } from "./version-history"
import { useNotes } from "./notes-provider"

type ViewMode = "edit" | "split" | "preview"

export function PageEditor() {
  const { currentPage, savePage } = useNotes()
  const [viewMode, setViewMode] = useState<ViewMode>("split")
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showVersions, setShowVersions] = useState(false)

  // Sync with currentPage when it changes
  useEffect(() => {
    if (currentPage) {
      setTitle(currentPage.title)
      setContent(currentPage.content)
      setDirty(false)
    }
  }, [currentPage])

  const handleContentChange = useCallback(
    (value: string | undefined) => {
      const newContent = value ?? ""
      setContent(newContent)
      if (currentPage && (newContent !== currentPage.content || title !== currentPage.title)) {
        setDirty(true)
      }
    },
    [currentPage, title],
  )

  const handleTitleChange = useCallback(
    (value: string) => {
      setTitle(value)
      if (currentPage && (value !== currentPage.title || content !== currentPage.content)) {
        setDirty(true)
      }
    },
    [currentPage, content],
  )

  const handleSave = useCallback(async () => {
    if (!currentPage || !dirty) return
    setSaving(true)
    try {
      await savePage(currentPage.id, title, content)
      setDirty(false)
    } finally {
      setSaving(false)
    }
  }, [currentPage, title, content, dirty, savePage])

  const handleEditorBeforeMount = useCallback((monaco: Monaco) => {
    monaco.editor.defineTheme("argus-light", {
      base: "vs",
      inherit: true,
      rules: [],
      colors: {
        "editor.background": "#EEEEEE",
      },
    })
  }, [])

  // Ctrl+S to save
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [handleSave])

  if (!currentPage) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <FileText className="h-12 w-12 mb-4" />
        <p className="text-lg font-medium">Select a page</p>
        <p className="text-sm">Choose a page from the list to start editing</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b shrink-0">
        <Input
          value={title}
          onChange={(e) => handleTitleChange(e.target.value)}
          className="h-8 font-semibold text-base border-none shadow-none focus-visible:ring-0 px-1"
          placeholder="Page title"
        />
        <Separator orientation="vertical" className="h-5" />
        <div className="flex items-center gap-0.5 bg-muted rounded-md p-0.5">
          <Button
            variant={viewMode === "edit" ? "secondary" : "ghost"}
            size="icon"
            className="h-7 w-7"
            onClick={() => setViewMode("edit")}
            title="Edit only"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant={viewMode === "split" ? "secondary" : "ghost"}
            size="icon"
            className="h-7 w-7"
            onClick={() => setViewMode("split")}
            title="Split view"
          >
            <Columns2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant={viewMode === "preview" ? "secondary" : "ghost"}
            size="icon"
            className="h-7 w-7"
            onClick={() => setViewMode("preview")}
            title="Preview only"
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
        </div>
        <Separator orientation="vertical" className="h-5" />
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={() => setShowVersions(true)}
        >
          <History className="h-3.5 w-3.5 mr-1" />
          v{currentPage.currentVersion}
        </Button>
        <Button
          size="sm"
          className="h-7 ml-auto"
          onClick={handleSave}
          disabled={!dirty || saving}
        >
          <Save className="h-3.5 w-3.5 mr-1" />
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>

      {/* Editor / Preview Area */}
      <div className="flex-1 min-h-0 flex">
        {(viewMode === "edit" || viewMode === "split") && (
          <div className={viewMode === "split" ? "w-1/2 border-r" : "w-full"}>
            <Editor
              height="100%"
              defaultLanguage="markdown"
              value={content}
              onChange={handleContentChange}
              beforeMount={handleEditorBeforeMount}
              theme="argus-light"
              options={{
                minimap: { enabled: false },
                lineNumbers: "on",
                wordWrap: "on",
                fontSize: 14,
                scrollBeyondLastLine: false,
                padding: { top: 12 },
              }}
            />
          </div>
        )}
        {(viewMode === "preview" || viewMode === "split") && (
          <div className={viewMode === "split" ? "w-1/2 overflow-auto" : "w-full overflow-auto"}>
            <MarkdownPreview content={content} />
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="flex items-center px-3 py-1.5 border-t text-xs text-muted-foreground shrink-0">
        <span>
          {dirty ? "Unsaved changes" : `Last saved ${new Date(currentPage.updatedAt).toLocaleString()}`}
        </span>
        <span className="ml-auto">Version {currentPage.currentVersion}</span>
      </div>

      {/* Version history sheet */}
      <VersionHistory open={showVersions} onOpenChange={setShowVersions} />
    </div>
  )
}
