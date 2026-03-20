"use client"

import { useCallback, useEffect, useState } from "react"
import { Plus, Server, Trash2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { DashboardHeader } from "@/components/dashboard-header"
import type { Platform } from "@/features/datasets/data/schema"

const BASE = "/api/v1/catalog"

async function fetchPlatforms(): Promise<Platform[]> {
  const res = await fetch(`${BASE}/platforms`)
  if (!res.ok) throw new Error(`Failed: ${res.status}`)
  return res.json()
}

async function createPlatform(payload: {
  name: string
  display_name: string
}): Promise<Platform> {
  const res = await fetch(`${BASE}/platforms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed: ${res.status}`)
  }
  return res.json()
}

async function deletePlatform(id: number): Promise<void> {
  const res = await fetch(`${BASE}/platforms/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed: ${res.status}`)
}

export default function PlatformsPage() {
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      setPlatforms(await fetchPlatforms())
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
    if (!name.trim() || !displayName.trim()) return
    setSaving(true)
    try {
      await createPlatform({
        name: name.trim().toLowerCase(),
        display_name: displayName.trim(),
      })
      setName("")
      setDisplayName("")
      setDialogOpen(false)
      await load()
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }, [name, displayName, load])

  const handleDelete = useCallback(
    async (id: number) => {
      try {
        await deletePlatform(id)
        await load()
      } catch {
        // ignore
      }
    },
    [load]
  )

  return (
    <>
      <DashboardHeader title="Platforms" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Data platforms that host your datasets
          </p>
          <Button size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Add Platform
          </Button>
        </div>

        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {isLoading ? (
            <p className="text-muted-foreground col-span-full text-center py-8">
              Loading platforms...
            </p>
          ) : platforms.length === 0 ? (
            <p className="text-muted-foreground col-span-full text-center py-8">
              No platforms configured.
            </p>
          ) : (
            platforms.map((p) => (
              <Card key={p.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Server className="h-5 w-5 text-muted-foreground" />
                      <CardTitle className="text-base">
                        {p.display_name}
                      </CardTitle>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleDelete(p.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground font-mono">
                    {p.name}
                  </p>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Add Platform</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="plat-name">Identifier</Label>
              <Input
                id="plat-name"
                placeholder="e.g. mysql, snowflake, kafka"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="plat-display">Display Name</Label>
              <Input
                id="plat-display"
                placeholder="e.g. MySQL, Snowflake, Apache Kafka"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
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
                disabled={saving || !name.trim() || !displayName.trim()}
              >
                {saving ? "Creating..." : "Create"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
