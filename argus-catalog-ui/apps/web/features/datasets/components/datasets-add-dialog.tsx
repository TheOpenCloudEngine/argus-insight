"use client"

import { useCallback, useEffect, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
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
import { Textarea } from "@workspace/ui/components/textarea"
import { createDataset, fetchPlatforms } from "../api"
import type { Platform } from "../data/schema"
import { useDatasets } from "./datasets-provider"

export function DatasetsAddDialog() {
  const { open, setOpen, refreshDatasets } = useDatasets()
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState("")
  const [platformId, setPlatformId] = useState("")
  const [description, setDescription] = useState("")
  const [origin, setOrigin] = useState("PROD")

  useEffect(() => {
    if (open === "add") {
      fetchPlatforms().then(setPlatforms).catch(() => {})
    }
  }, [open])

  const handleSubmit = useCallback(async () => {
    if (!name.trim() || !platformId) return
    setSaving(true)
    setError(null)
    try {
      await createDataset({
        name: name.trim(),
        platform_id: Number(platformId),
        description: description.trim() || undefined,
        origin,
      })
      setName("")
      setPlatformId("")
      setDescription("")
      setOrigin("PROD")
      setOpen(null)
      await refreshDatasets()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create dataset")
    } finally {
      setSaving(false)
    }
  }, [name, platformId, description, origin, setOpen, refreshDatasets])

  return (
    <Dialog open={open === "add"} onOpenChange={() => setOpen(null)}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add Dataset</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label htmlFor="ds-name">Name</Label>
            <Input
              id="ds-name"
              placeholder="e.g. user_events"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ds-platform">Platform</Label>
            <Select value={platformId} onValueChange={setPlatformId}>
              <SelectTrigger id="ds-platform">
                <SelectValue placeholder="Select platform" />
              </SelectTrigger>
              <SelectContent>
                {platforms.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ds-origin">Environment</Label>
            <Select value={origin} onValueChange={setOrigin}>
              <SelectTrigger id="ds-origin">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="PROD">PROD</SelectItem>
                <SelectItem value="DEV">DEV</SelectItem>
                <SelectItem value="STAGING">STAGING</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ds-desc">Description</Label>
            <Textarea
              id="ds-desc"
              placeholder="What does this dataset contain?"
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
              disabled={saving || !name.trim() || !platformId}
            >
              {saving ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
