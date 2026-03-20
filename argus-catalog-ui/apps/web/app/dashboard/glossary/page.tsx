"use client"

import { useCallback, useEffect, useState } from "react"
import { Plus, Trash2 } from "lucide-react"

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
import { Textarea } from "@workspace/ui/components/textarea"
import { DashboardHeader } from "@/components/dashboard-header"
import {
  createGlossaryTerm,
  deleteGlossaryTerm,
  fetchGlossaryTerms,
} from "@/features/glossary/api"
import type { GlossaryTerm } from "@/features/datasets/data/schema"

export default function GlossaryPage() {
  const [terms, setTerms] = useState<GlossaryTerm[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [source, setSource] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      setTerms(await fetchGlossaryTerms())
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
      await createGlossaryTerm({
        name: name.trim(),
        description: description.trim() || undefined,
        source: source.trim() || undefined,
      })
      setName("")
      setDescription("")
      setSource("")
      setDialogOpen(false)
      await load()
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }, [name, description, source, load])

  const handleDelete = useCallback(
    async (termId: number) => {
      try {
        await deleteGlossaryTerm(termId)
        await load()
      } catch {
        // ignore
      }
    },
    [load]
  )

  return (
    <>
      <DashboardHeader title="Business Glossary" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Define and manage business glossary terms for your data assets
          </p>
          <Button size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Add Term
          </Button>
        </div>

        <div className="grid gap-3">
          {isLoading ? (
            <p className="text-muted-foreground text-center py-8">
              Loading glossary terms...
            </p>
          ) : terms.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No glossary terms yet. Create one to get started.
            </p>
          ) : (
            terms.map((term) => (
              <Card key={term.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{term.name}</CardTitle>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleDelete(term.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm">
                    {term.description || "No description"}
                  </p>
                  {term.source && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Source: {term.source}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Glossary Term</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="term-name">Name</Label>
              <Input
                id="term-name"
                placeholder="e.g. Customer Lifetime Value"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="term-desc">Description</Label>
              <Textarea
                id="term-desc"
                placeholder="Define this business term..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="term-source">Source</Label>
              <Input
                id="term-source"
                placeholder="e.g. Marketing Team, Data Dictionary"
                value={source}
                onChange={(e) => setSource(e.target.value)}
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
                disabled={saving || !name.trim()}
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
