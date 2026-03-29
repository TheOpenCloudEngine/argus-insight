"use client"

import { useMemo, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Button } from "@workspace/ui/components/button"
import { Badge } from "@workspace/ui/components/badge"
import { Input } from "@workspace/ui/components/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Plus, Search, PackageOpen } from "lucide-react"
import type { PluginResponse } from "@/features/software-deployment/types"

interface AddStepDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  allPlugins: PluginResponse[]
  pipelinePluginNames: string[]
  onAdd: (plugin: PluginResponse) => void
}

const ALL_CATEGORIES = "__all__"

export function AddStepDialog({
  open,
  onOpenChange,
  allPlugins,
  pipelinePluginNames,
  onAdd,
}: AddStepDialogProps) {
  const [search, setSearch] = useState("")
  const [category, setCategory] = useState(ALL_CATEGORIES)

  // Reset filters when dialog opens
  const handleOpenChange = (value: boolean) => {
    if (value) {
      setSearch("")
      setCategory(ALL_CATEGORIES)
    }
    onOpenChange(value)
  }

  const pipelineSet = useMemo(
    () => new Set(pipelinePluginNames),
    [pipelinePluginNames],
  )

  const categories = useMemo(() => {
    const cats = new Set<string>()
    for (const p of allPlugins) {
      if (p.category) cats.add(p.category)
    }
    return Array.from(cats).sort()
  }, [allPlugins])

  const filteredPlugins = useMemo(() => {
    const query = search.toLowerCase().trim()

    return allPlugins.filter((plugin) => {
      // Exclude already-added plugins
      if (pipelineSet.has(plugin.name)) return false

      // Category filter
      if (category !== ALL_CATEGORIES && plugin.category !== category) return false

      // Search filter
      if (query) {
        const haystack = [
          plugin.name,
          plugin.display_name,
          plugin.description,
          ...plugin.tags,
        ]
          .join(" ")
          .toLowerCase()
        if (!haystack.includes(query)) return false
      }

      return true
    })
  }, [allPlugins, pipelineSet, category, search])

  const allFiltered = allPlugins.filter((p) => !pipelineSet.has(p.name))
  const isAllInPipeline = allFiltered.length === 0
  const isSearchEmpty = filteredPlugins.length === 0 && !isAllInPipeline

  function handleAdd(plugin: PluginResponse) {
    onAdd(plugin)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add Plugin to Pipeline</DialogTitle>
          <DialogDescription>
            Select a plugin to add as a new step in the deployment pipeline.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {/* Search and category filter */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="text-muted-foreground absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" />
              <Input
                placeholder="Search plugins..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_CATEGORIES}>All Categories</SelectItem>
                {categories.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Plugin list */}
          <div className="max-h-96 overflow-y-auto">
            {isAllInPipeline && (
              <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
                <PackageOpen className="text-muted-foreground h-10 w-10" />
                <p className="text-muted-foreground text-sm">
                  All plugins are already in the pipeline.
                </p>
              </div>
            )}

            {isSearchEmpty && (
              <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
                <Search className="text-muted-foreground h-10 w-10" />
                <p className="text-muted-foreground text-sm">
                  No plugins match your search.
                </p>
              </div>
            )}

            {filteredPlugins.length > 0 && (
              <div className="flex flex-col gap-2">
                {filteredPlugins.map((plugin) => (
                  <div
                    key={plugin.name}
                    className="flex items-start justify-between gap-4 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {plugin.display_name}
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {plugin.category}
                        </Badge>
                        <Badge variant="secondary" className="text-xs">
                          {plugin.source}
                        </Badge>
                      </div>
                      <p className="text-muted-foreground text-sm">
                        {plugin.description}
                      </p>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>
                          {plugin.versions.length} version
                          {plugin.versions.length !== 1 ? "s" : ""}
                        </span>
                        {plugin.depends_on.length > 0 && (
                          <span>
                            Depends on: {plugin.depends_on.join(", ")}
                          </span>
                        )}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleAdd(plugin)}
                    >
                      <Plus className="mr-1 h-4 w-4" />
                      Add
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
