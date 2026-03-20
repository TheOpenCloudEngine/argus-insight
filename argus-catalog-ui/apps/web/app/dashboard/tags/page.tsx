"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { AlertTriangle, Database, Plus, Trash2 } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Separator } from "@workspace/ui/components/separator"
import { DashboardHeader } from "@/components/dashboard-header"
import {
  createTag,
  deleteTag,
  fetchTags,
  fetchTagUsage,
  type TagUsage,
} from "@/features/tags/api"
import type { Tag } from "@/features/datasets/data/schema"

export default function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Create dialog
  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [color, setColor] = useState("#3b82f6")
  const [saving, setSaving] = useState(false)

  // Delete confirm dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<TagUsage | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      setTags(await fetchTags())
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleCreate = useCallback(async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await createTag({
        name: name.trim(),
        description: description.trim() || undefined,
        color,
      })
      setName("")
      setDescription("")
      setColor("#3b82f6")
      setDialogOpen(false)
      await load()
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }, [name, description, color, load])

  // Open delete dialog: fetch usage first
  const handleDeleteClick = useCallback(async (tagId: number) => {
    setDeleteLoading(true)
    setDeleteDialogOpen(true)
    setDeleteTarget(null)
    try {
      const usage = await fetchTagUsage(tagId)
      setDeleteTarget(usage)
    } catch {
      setDeleteDialogOpen(false)
    } finally {
      setDeleteLoading(false)
    }
  }, [])

  // Confirm delete
  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteTag(deleteTarget.tag.id)
      setDeleteDialogOpen(false)
      setDeleteTarget(null)
      await load()
    } catch {
      // ignore
    } finally {
      setDeleting(false)
    }
  }, [deleteTarget, load])

  return (
    <>
      <DashboardHeader title="Tags" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Manage tags for categorizing datasets
          </p>
          <Button size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Add Tag
          </Button>
        </div>

        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {isLoading ? (
            <p className="text-muted-foreground col-span-full text-center py-8">
              Loading tags...
            </p>
          ) : tags.length === 0 ? (
            <p className="text-muted-foreground col-span-full text-center py-8">
              No tags yet. Create one to get started.
            </p>
          ) : (
            tags.map((tag) => (
              <Card key={tag.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge
                        style={{ backgroundColor: tag.color, color: "#fff" }}
                      >
                        {tag.name}
                      </Badge>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleDeleteClick(tag.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {tag.description || "No description"}
                  </p>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* Create Tag Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Add Tag</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="tag-name">Name</Label>
              <Input
                id="tag-name"
                placeholder="e.g. PII, deprecated, tier-1"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tag-desc">Description</Label>
              <Input
                id="tag-desc"
                placeholder="Optional description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tag-color">Color</Label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  id="tag-color"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  className="h-9 w-12 cursor-pointer rounded border"
                />
                <Input
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  className="flex-1"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                onClick={() => setDialogOpen(false)}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={saving || !name.trim()}
              >
                {saving ? "Creating..." : "Create"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog with Usage Info */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Delete Tag
            </DialogTitle>
            {deleteTarget && (
              <DialogDescription>
                Are you sure you want to delete the tag{" "}
                <Badge
                  style={{
                    backgroundColor: deleteTarget.tag.color,
                    color: "#fff",
                  }}
                  className="text-xs mx-0.5"
                >
                  {deleteTarget.tag.name}
                </Badge>
                ?
              </DialogDescription>
            )}
          </DialogHeader>

          {deleteLoading ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              Checking tag usage...
            </div>
          ) : deleteTarget ? (
            <div className="space-y-3">
              {deleteTarget.total_datasets > 0 ? (
                <>
                  <div className="rounded-md border border-destructive/20 bg-destructive/5 p-3">
                    <p className="text-sm font-medium text-destructive">
                      This tag is used in {deleteTarget.total_datasets} dataset
                      {deleteTarget.total_datasets !== 1 ? "s" : ""}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Deleting this tag will remove it from all datasets below.
                    </p>
                  </div>

                  <div className="max-h-[200px] overflow-y-auto rounded-md border">
                    {deleteTarget.datasets.map((ds) => (
                      <div
                        key={ds.id}
                        className="flex items-center gap-2 px-3 py-2 text-sm border-b last:border-b-0"
                      >
                        <Database className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <Link
                          href={`/dashboard/datasets/${ds.id}`}
                          className="font-medium hover:underline truncate"
                          onClick={() => setDeleteDialogOpen(false)}
                        >
                          {ds.name}
                        </Link>
                        <Badge variant="outline" className="text-xs shrink-0 ml-auto">
                          {ds.platform_display_name}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="rounded-md border bg-muted/30 p-3">
                  <p className="text-sm text-muted-foreground">
                    This tag is not used by any datasets. It can be safely deleted.
                  </p>
                </div>
              )}
            </div>
          ) : null}

          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={deleting}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleting || deleteLoading || !deleteTarget}
            >
              {deleting ? "Deleting..." : "Delete Tag"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
