"use client"

import { useCallback, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Textarea } from "@workspace/ui/components/textarea"
import { createModel } from "../api"
import { useModels } from "./models-provider"

export function ModelsAddDialog() {
  const { open, setOpen, refreshModels } = useModels()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState("")
  const [owner, setOwner] = useState("")
  const [description, setDescription] = useState("")

  const handleSubmit = useCallback(async () => {
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    try {
      await createModel({
        name: name.trim(),
        owner: owner.trim() || undefined,
        description: description.trim() || undefined,
      })
      setName("")
      setOwner("")
      setDescription("")
      setOpen(null)
      await refreshModels()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create model")
    } finally {
      setSaving(false)
    }
  }, [name, owner, description, setOpen, refreshModels])

  return (
    <Dialog open={open === "add"} onOpenChange={() => setOpen(null)}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add Model</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label htmlFor="model-name">Name</Label>
            <Input
              id="model-name"
              placeholder="e.g. argus.ml.iris_classifier"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Use 3-part name: catalog.schema.model
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="model-owner">Owner</Label>
            <Input
              id="model-owner"
              placeholder="e.g. data-team"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="model-desc">Description</Label>
            <Textarea
              id="model-desc"
              placeholder="What does this model do?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => setOpen(null)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={saving || !name.trim()}
            >
              {saving ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
