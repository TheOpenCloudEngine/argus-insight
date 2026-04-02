"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { CommentEditor } from "@/components/comments/comment-editor"
import { createVocIssue } from "@/features/voc/api"
import { fetchWorkspaces, fetchWorkspaceServices } from "@/features/workspaces/api"
import type { WorkspaceResponse, WorkspaceService } from "@/features/workspaces/types"

interface VocCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

export function VocCreateDialog({ open, onOpenChange, onCreated }: VocCreateDialogProps) {
  const [title, setTitle] = useState("")
  const [category, setCategory] = useState("general")
  const [priority, setPriority] = useState("medium")
  const [workspaceId, setWorkspaceId] = useState<string>("none")
  const [serviceId, setServiceId] = useState<string>("none")
  const [description, setDescription] = useState("")
  const [submitting, setSubmitting] = useState(false)

  // Resource request fields
  const [resourceType, setResourceType] = useState("cpu")
  const [resourceCurrent, setResourceCurrent] = useState("")
  const [resourceRequested, setResourceRequested] = useState("")

  // Dynamic data
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([])
  const [services, setServices] = useState<WorkspaceService[]>([])

  // Load workspaces on open
  useEffect(() => {
    if (!open) return
    fetchWorkspaces(1, 100, "active")
      .then((data) => setWorkspaces(data.items))
      .catch(() => {})
  }, [open])

  // Load services when workspace changes — only running services
  useEffect(() => {
    if (workspaceId === "none") {
      setServices([])
      setServiceId("none")
      return
    }
    fetchWorkspaceServices(Number(workspaceId))
      .then((svcs) => setServices(svcs.filter((s) => s.status === "running")))
      .catch(() => setServices([]))
  }, [workspaceId])

  const reset = () => {
    setTitle("")
    setCategory("general")
    setPriority("medium")
    setWorkspaceId("none")
    setServiceId("none")
    setDescription("")
    setResourceType("cpu")
    setResourceCurrent("")
    setResourceRequested("")
  }

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) return
    setSubmitting(true)
    try {
      const ws = workspaces.find((w) => String(w.id) === workspaceId)
      const svc = services.find((s) => String(s.id) === serviceId)
      await createVocIssue({
        title: title.trim(),
        description,
        category,
        priority,
        workspace_id: ws?.id ?? null,
        workspace_name: ws?.display_name ?? ws?.name ?? null,
        service_id: svc?.id ?? null,
        service_name: svc?.display_name ?? svc?.plugin_name ?? null,
        resource_detail: category === "resource_request" && resourceType
          ? { resource_type: resourceType, current: resourceCurrent, requested: resourceRequested }
          : null,
      })
      reset()
      onCreated()
    } catch (e) {
      console.error("Failed to create VOC:", e)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New Issue</DialogTitle>
          <DialogDescription className="text-sm">
            Submit a request, report an issue, or ask a question.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Title */}
          <div className="space-y-1.5">
            <Label className="text-sm">Title</Label>
            <Input
              placeholder="Brief summary of your issue"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="text-sm"
            />
          </div>

          {/* Category & Priority */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-sm">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem className="text-sm" value="general">General</SelectItem>
                  <SelectItem className="text-sm" value="resource_request">Resource Request</SelectItem>
                  <SelectItem className="text-sm" value="service_issue">Service Issue</SelectItem>
                  <SelectItem className="text-sm" value="feature_request">Feature Request</SelectItem>
                  <SelectItem className="text-sm" value="account">Account</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Priority</Label>
              <Select value={priority} onValueChange={setPriority}>
                <SelectTrigger className="h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem className="text-sm" value="low">Low</SelectItem>
                  <SelectItem className="text-sm" value="medium">Medium</SelectItem>
                  <SelectItem className="text-sm" value="high">High</SelectItem>
                  <SelectItem className="text-sm" value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Workspace & Service (optional) */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-sm">Workspace <span className="text-muted-foreground">(optional)</span></Label>
              <Select value={workspaceId} onValueChange={setWorkspaceId}>
                <SelectTrigger className="h-9 text-sm">
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem className="text-sm" value="none">None</SelectItem>
                  {workspaces.map((ws) => (
                    <SelectItem key={ws.id} value={String(ws.id)}>
                      {ws.display_name || ws.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Service <span className="text-muted-foreground">(optional)</span></Label>
              <Select
                value={serviceId}
                onValueChange={setServiceId}
                disabled={workspaceId === "none" || services.length === 0}
              >
                <SelectTrigger className="h-9 text-sm">
                  <SelectValue placeholder={workspaceId === "none" ? "Select workspace first" : "None"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem className="text-sm" value="none">None</SelectItem>
                  {services.map((svc) => (
                    <SelectItem key={svc.id} value={String(svc.id)}>
                      {svc.display_name || svc.plugin_name}
                      {svc.version && ` v${svc.version}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Resource request detail */}
          {category === "resource_request" && (
            <div className="grid grid-cols-3 gap-4 rounded-lg border p-3 bg-muted/30">
              <div className="space-y-1.5">
                <Label className="text-sm">Resource Type</Label>
                <Select value={resourceType} onValueChange={setResourceType}>
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem className="text-sm" value="cpu">CPU</SelectItem>
                    <SelectItem className="text-sm" value="memory">Memory</SelectItem>
                    <SelectItem className="text-sm" value="gpu">GPU</SelectItem>
                    <SelectItem className="text-sm" value="disk">Disk</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Current</Label>
                <Input
                  placeholder="e.g. 2Gi"
                  value={resourceCurrent}
                  onChange={(e) => setResourceCurrent(e.target.value)}
                  className="h-9 text-sm"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Requested</Label>
                <Input
                  placeholder="e.g. 8Gi"
                  value={resourceRequested}
                  onChange={(e) => setResourceRequested(e.target.value)}
                  className="h-9 text-sm"
                  className="h-9"
                />
              </div>
            </div>
          )}

          {/* Description (rich text editor) */}
          <div className="space-y-1.5">
            <Label className="text-sm">Description</Label>
            <CommentEditor
              onSubmit={async () => {}}
              placeholder="Describe your issue in detail..."
              hideFooter
              minHeight="160px"
              onChange={(html, _plain, isEmpty) => {
                setDescription(isEmpty ? "" : html)
              }}
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting || !title.trim() || !description.trim()}>
              {submitting && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Submit
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
