"use client"

import { useCallback, useEffect, useState } from "react"
import { Clock, FileCode, Loader2, Save, Trash2, Upload } from "lucide-react"
import Editor from "@monaco-editor/react"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { authFetch } from "@/features/auth/auth-fetch"

// ── Save Pipeline Dialog ─────────────────────────────────────

interface SaveDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: number
  pipelineJson: Record<string, any>
  /** If editing existing pipeline, pass its id + name */
  existingId?: number | null
  existingName?: string
  existingDescription?: string
  onSaved: (id: number, name: string) => void
}

export function SavePipelineDialog({
  open,
  onOpenChange,
  workspaceId,
  pipelineJson,
  existingId,
  existingName,
  existingDescription,
  onSaved,
}: SaveDialogProps) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setName(existingName || "")
      setDescription(existingDescription || "")
    }
  }, [open, existingName, existingDescription])

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      if (existingId) {
        // Update existing
        const res = await authFetch(`/api/v1/ml-studio/pipelines/${existingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim(), description: description.trim(), pipeline_json: pipelineJson }),
        })
        if (res.ok) {
          onSaved(existingId, name.trim())
          onOpenChange(false)
        }
      } else {
        // Create new
        const res = await authFetch("/api/v1/ml-studio/pipelines", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            workspace_id: workspaceId,
            name: name.trim(),
            description: description.trim(),
            pipeline_json: pipelineJson,
          }),
        })
        if (res.ok) {
          const data = await res.json()
          onSaved(data.id, data.name)
          onOpenChange(false)
        }
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm">{existingId ? "Update Pipeline" : "Save Pipeline"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label className="text-sm">Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My ML Pipeline"
              className="h-8 text-sm"
              autoFocus
            />
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Description (optional)</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Classification pipeline for customer churn"
              className="h-8 text-sm"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" size="sm" className="text-sm" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button size="sm" className="text-sm" onClick={handleSave} disabled={saving || !name.trim()}>
            {saving ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Save className="mr-1.5 h-3.5 w-3.5" />}
            {existingId ? "Update" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Load Pipeline Dialog ─────────────────────────────────────

interface PipelineItem {
  id: number
  name: string
  description: string
  author_username: string | null
  created_at: string
  updated_at: string
}

interface LoadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: number
  onLoad: (id: number, name: string, description: string, pipelineJson: Record<string, any>) => void
}

export function LoadPipelineDialog({
  open,
  onOpenChange,
  workspaceId,
  onLoad,
}: LoadDialogProps) {
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)

  const fetchPipelines = useCallback(async () => {
    if (!workspaceId || !open) return
    setLoading(true)
    try {
      const res = await authFetch(`/api/v1/ml-studio/pipelines?workspace_id=${workspaceId}`)
      if (res.ok) {
        const data = await res.json()
        setPipelines(data.pipelines || [])
      }
    } finally {
      setLoading(false)
    }
  }, [workspaceId, open])

  useEffect(() => {
    if (open) fetchPipelines()
  }, [open, fetchPipelines])

  const handleLoad = async (id: number) => {
    const res = await authFetch(`/api/v1/ml-studio/pipelines/${id}`)
    if (res.ok) {
      const data = await res.json()
      onLoad(data.id, data.name, data.description, data.pipeline_json)
      onOpenChange(false)
    }
  }

  const handleDelete = async (id: number) => {
    setDeleting(id)
    try {
      const res = await authFetch(`/api/v1/ml-studio/pipelines/${id}`, { method: "DELETE" })
      if (res.ok) {
        setPipelines((prev) => prev.filter((p) => p.id !== id))
      }
    } finally {
      setDeleting(null)
    }
  }

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[70vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm">Load Pipeline</DialogTitle>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto space-y-1">
          {loading ? (
            <div className="flex items-center justify-center h-[200px]">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : pipelines.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground">
              <FileCode className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-sm">No saved pipelines</p>
            </div>
          ) : (
            pipelines.map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/50 cursor-pointer transition-colors"
                onClick={() => handleLoad(p.id)}
              >
                <FileCode className="h-5 w-5 text-primary shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{p.name}</p>
                  {p.description && (
                    <p className="text-[11px] text-muted-foreground truncate">{p.description}</p>
                  )}
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[11px] text-muted-foreground flex items-center gap-0.5">
                      <Clock className="h-3 w-3" /> {formatDate(p.updated_at)}
                    </span>
                    {p.author_username && (
                      <span className="text-[11px] text-muted-foreground">{p.author_username}</span>
                    )}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(p.id)
                  }}
                  disabled={deleting === p.id}
                >
                  {deleting === p.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  )}
                </Button>
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Code Preview Dialog (Monaco Editor) ──────────────────────

interface PreviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  code: string
}

export function CodePreviewDialog({
  open,
  onOpenChange,
  code,
}: PreviewDialogProps) {
  const handleCopy = () => {
    navigator.clipboard.writeText(code)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm flex items-center gap-2">
            <FileCode className="h-4 w-4" />
            Generated Python Code
          </DialogTitle>
        </DialogHeader>

        <div className="rounded border overflow-hidden" style={{ height: "60vh" }}>
          <Editor
            height="100%"
            language="python"
            value={code}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontFamily: "'D2Coding', 'D2 Coding', monospace",
              fontSize: 13,
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              wordWrap: "off",
              automaticLayout: true,
              renderLineHighlight: "all",
              padding: { top: 8 },
              domReadOnly: true,
            }}
            theme="vs-dark"
          />
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm" className="text-sm" onClick={handleCopy}>
            Copy to Clipboard
          </Button>
          <Button variant="outline" size="sm" className="text-sm" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
