"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  BookOpen,
  ChevronRight,
  Grid3X3,
  List,
  Plus,
  Search,
  Trash2,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent } from "@workspace/ui/components/card"
import { Checkbox } from "@workspace/ui/components/checkbox"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@workspace/ui/components/command"
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
import { Popover, PopoverContent, PopoverTrigger } from "@workspace/ui/components/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Textarea } from "@workspace/ui/components/textarea"
import { DashboardHeader } from "@/components/dashboard-header"
import {
  createGlossaryTerm,
  deleteGlossaryTerm,
  fetchGlossaryTerms,
} from "@/features/glossary/api"
import type { GlossaryTerm } from "@/features/datasets/data/schema"

// ---------------------------------------------------------------------------
// Tree node type
// ---------------------------------------------------------------------------
type TreeNode = GlossaryTerm & { children: TreeNode[]; depth: number }

function buildTree(terms: GlossaryTerm[]): TreeNode[] {
  const map = new Map<number, TreeNode>()
  const roots: TreeNode[] = []

  for (const t of terms) {
    map.set(t.id, { ...t, children: [], depth: 0 })
  }
  for (const node of map.values()) {
    if (node.parent_id && map.has(node.parent_id)) {
      const parent = map.get(node.parent_id)!
      node.depth = parent.depth + 1
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  }
  // Sort alphabetically
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name))
    for (const n of nodes) sortNodes(n.children)
  }
  sortNodes(roots)
  return roots
}

function flattenTree(nodes: TreeNode[]): TreeNode[] {
  const result: TreeNode[] = []
  const walk = (list: TreeNode[]) => {
    for (const n of list) {
      result.push(n)
      walk(n.children)
    }
  }
  walk(nodes)
  return result
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function GlossaryPage() {
  const [terms, setTerms] = useState<GlossaryTerm[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // View mode
  const [viewMode, setViewMode] = useState<"grid" | "tree">("grid")

  // Filter state
  const [searchQuery, setSearchQuery] = useState("")
  const [sourceFilter, setSourceFilter] = useState("all")

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  // Tree expanded state
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  // Add dialog state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [source, setSource] = useState("")
  const [sourcePopoverOpen, setSourcePopoverOpen] = useState(false)
  const [parentId, setParentId] = useState<string>("none")
  const [parentPopoverOpen, setParentPopoverOpen] = useState(false)
  const [parentSearch, setParentSearch] = useState("")
  const [saving, setSaving] = useState(false)

  // Delete confirm dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      setTerms(await fetchGlossaryTerms())
      setSelectedIds(new Set())
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Derived: unique sources
  const sources = useMemo(
    () =>
      Array.from(new Set(terms.map((t) => t.source).filter(Boolean) as string[])).sort(),
    [terms]
  )

  // Derived: term map for parent lookups
  const termMap = useMemo(() => {
    const m = new Map<number, GlossaryTerm>()
    for (const t of terms) m.set(t.id, t)
    return m
  }, [terms])

  // Derived: children count map
  const childrenCount = useMemo(() => {
    const m = new Map<number, number>()
    for (const t of terms) {
      if (t.parent_id) {
        m.set(t.parent_id, (m.get(t.parent_id) ?? 0) + 1)
      }
    }
    return m
  }, [terms])

  // Derived: filtered terms
  const filtered = useMemo(() => {
    let result = terms
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          (t.description ?? "").toLowerCase().includes(q)
      )
    }
    if (sourceFilter !== "all") {
      result = result.filter((t) => t.source === sourceFilter)
    }
    return result
  }, [terms, searchQuery, sourceFilter])

  // Derived: tree structure (for tree view, only when no search filter)
  const tree = useMemo(() => buildTree(filtered), [filtered])
  const flatTree = useMemo(() => flattenTree(tree), [tree])

  // Selection helpers
  const allSelected = filtered.length > 0 && filtered.every((t) => selectedIds.has(t.id))

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map((t) => t.id)))
    }
  }

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const expandAll = () => {
    setExpandedIds(new Set(terms.filter((t) => childrenCount.has(t.id)).map((t) => t.id)))
  }

  const collapseAll = () => {
    setExpandedIds(new Set())
  }

  // Create
  const handleCreate = useCallback(async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await createGlossaryTerm({
        name: name.trim(),
        description: description.trim() || undefined,
        source: source.trim() || undefined,
        parent_id: parentId !== "none" ? Number(parentId) : undefined,
      })
      setName("")
      setDescription("")
      setSource("")
      setParentId("none")
      setDialogOpen(false)
      await load()
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }, [name, description, source, parentId, load])

  // Bulk delete
  const handleBulkDelete = useCallback(async () => {
    setDeleting(true)
    try {
      await Promise.all(Array.from(selectedIds).map((id) => deleteGlossaryTerm(id)))
      setDeleteDialogOpen(false)
      await load()
    } catch {
      // ignore
    } finally {
      setDeleting(false)
    }
  }, [selectedIds, load])

  // Parent name helper
  const parentName = (pid: number | null | undefined) => {
    if (!pid) return null
    return termMap.get(pid)?.name ?? null
  }

  // Visible tree nodes (respecting expanded state)
  const visibleTreeNodes = useMemo(() => {
    const result: TreeNode[] = []
    const walk = (nodes: TreeNode[]) => {
      for (const n of nodes) {
        result.push(n)
        if (n.children.length > 0 && expandedIds.has(n.id)) {
          walk(n.children)
        }
      }
    }
    walk(tree)
    return result
  }, [tree, expandedIds])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <>
      <DashboardHeader title="Business Glossary" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Toolbar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-1 items-center gap-2">
            {/* Search */}
            <div className="relative max-w-xs flex-1">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search terms..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 h-9"
              />
            </div>
            {/* Source filter */}
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger size="sm" className="w-[160px]">
                <SelectValue placeholder="All Sources" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sources</SelectItem>
                {sources.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {/* Clear filters */}
            {(searchQuery || sourceFilter !== "all") && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearchQuery("")
                  setSourceFilter("all")
                }}
              >
                Clear
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* View toggle */}
            <div className="flex items-center border rounded-md">
              <Button
                variant={viewMode === "grid" ? "secondary" : "ghost"}
                size="icon-sm"
                onClick={() => setViewMode("grid")}
                aria-label="Grid view"
              >
                <Grid3X3 className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant={viewMode === "tree" ? "secondary" : "ghost"}
                size="icon-sm"
                onClick={() => setViewMode("tree")}
                aria-label="Tree view"
              >
                <List className="h-3.5 w-3.5" />
              </Button>
            </div>
            {/* Add */}
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <Plus className="mr-1 h-3.5 w-3.5" />
              Add Term
            </Button>
            {/* Bulk delete */}
            <Button
              variant="destructive"
              size="sm"
              disabled={selectedIds.size === 0}
              onClick={() => setDeleteDialogOpen(true)}
            >
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              Delete{selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}
            </Button>
          </div>
        </div>

        {/* Select all bar */}
        {filtered.length > 0 && (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Checkbox
                checked={allSelected}
                onCheckedChange={toggleSelectAll}
                aria-label="Select all"
              />
              <span>
                {selectedIds.size > 0
                  ? `${selectedIds.size} of ${filtered.length} selected`
                  : `${filtered.length} term${filtered.length !== 1 ? "s" : ""}`}
              </span>
            </div>
            {viewMode === "tree" && (
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" onClick={expandAll}>
                  Expand All
                </Button>
                <Button variant="ghost" size="sm" onClick={collapseAll}>
                  Collapse All
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Content */}
        {isLoading ? (
          <div className="text-muted-foreground text-center py-12">
            Loading glossary terms...
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-muted-foreground text-center py-12">
            {terms.length === 0
              ? "No glossary terms yet. Create one to get started."
              : "No terms match the current filters."}
          </div>
        ) : viewMode === "grid" ? (
          /* =================== Grid View =================== */
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map((term) => {
              const parent = parentName(term.parent_id)
              const children = childrenCount.get(term.id) ?? 0
              const isSelected = selectedIds.has(term.id)
              return (
                <Card
                  key={term.id}
                  className={`relative cursor-pointer transition-colors ${
                    isSelected
                      ? "ring-2 ring-primary"
                      : "hover:border-muted-foreground/30"
                  }`}
                  onClick={() => toggleSelect(term.id)}
                >
                  <div className="absolute top-3 left-3">
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => toggleSelect(term.id)}
                      onClick={(e) => e.stopPropagation()}
                      aria-label={`Select ${term.name}`}
                    />
                  </div>
                  <CardContent className="pt-4 pl-10 pr-4 pb-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <BookOpen className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <h3 className="font-semibold text-sm truncate">
                          {term.name}
                        </h3>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1.5 line-clamp-2">
                        {term.description || "No description"}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 mt-3">
                      {term.source && (
                        <Badge variant="secondary" className="text-xs">
                          {term.source}
                        </Badge>
                      )}
                      {parent && (
                        <Badge variant="outline" className="text-xs">
                          Parent: {parent}
                        </Badge>
                      )}
                      {children > 0 && (
                        <Badge variant="outline" className="text-xs">
                          {children} children
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        ) : (
          /* =================== Tree View =================== */
          <div className="border rounded-lg divide-y">
            {visibleTreeNodes.map((node) => {
              const isSelected = selectedIds.has(node.id)
              const hasChildren = node.children.length > 0
              const isExpanded = expandedIds.has(node.id)
              return (
                <div
                  key={node.id}
                  className={`flex items-center gap-2 px-3 py-2.5 hover:bg-muted/50 transition-colors ${
                    isSelected ? "bg-primary/5" : ""
                  }`}
                  style={{ paddingLeft: `${node.depth * 28 + 12}px` }}
                >
                  {/* Expand/collapse toggle */}
                  <button
                    className={`shrink-0 p-0.5 rounded hover:bg-muted ${
                      hasChildren ? "cursor-pointer" : "invisible"
                    }`}
                    onClick={() => hasChildren && toggleExpand(node.id)}
                    tabIndex={hasChildren ? 0 : -1}
                  >
                    <ChevronRight
                      className={`h-3.5 w-3.5 transition-transform ${
                        isExpanded ? "rotate-90" : ""
                      }`}
                    />
                  </button>

                  {/* Checkbox */}
                  <Checkbox
                    checked={isSelected}
                    onCheckedChange={() => toggleSelect(node.id)}
                    aria-label={`Select ${node.name}`}
                    className="shrink-0"
                  />

                  {/* Content */}
                  <div className="flex-1 min-w-0 flex items-center gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-sm truncate">
                          {node.name}
                        </span>
                        {hasChildren && (
                          <span className="text-xs text-muted-foreground shrink-0">
                            ({node.children.length})
                          </span>
                        )}
                      </div>
                      {node.description && (
                        <p className="text-xs text-muted-foreground truncate max-w-lg">
                          {node.description}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {node.source && (
                        <Badge variant="secondary" className="text-xs">
                          {node.source}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* =================== Add Term Dialog =================== */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Glossary Term</DialogTitle>
            <DialogDescription>
              Define a new business glossary term.
            </DialogDescription>
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

            {/* Source - combobox: select existing or type new */}
            <div className="grid gap-2">
              <Label>Source</Label>
              <Popover open={sourcePopoverOpen} onOpenChange={setSourcePopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="justify-start font-normal h-9"
                  >
                    {source || (
                      <span className="text-muted-foreground">
                        Select or type source...
                      </span>
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="p-0 w-[--radix-popover-trigger-width]" align="start">
                  <Command>
                    <CommandInput
                      placeholder="Search or type new..."
                      value={source}
                      onValueChange={setSource}
                    />
                    <CommandList>
                      <CommandEmpty>
                        {source.trim() ? (
                          <button
                            className="w-full text-left px-2 py-1.5 text-sm hover:bg-accent rounded cursor-pointer"
                            onClick={() => setSourcePopoverOpen(false)}
                          >
                            Use &quot;{source.trim()}&quot;
                          </button>
                        ) : (
                          "Type a source name"
                        )}
                      </CommandEmpty>
                      <CommandGroup>
                        {sources.map((s) => (
                          <CommandItem
                            key={s}
                            value={s}
                            onSelect={(val) => {
                              setSource(val)
                              setSourcePopoverOpen(false)
                            }}
                          >
                            {s}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Parent term - searchable combobox */}
            <div className="grid gap-2">
              <Label>Parent Term</Label>
              <Popover open={parentPopoverOpen} onOpenChange={setParentPopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="justify-start font-normal h-9"
                  >
                    {parentId !== "none" ? (
                      termMap.get(Number(parentId))?.name ?? "Unknown"
                    ) : (
                      <span className="text-muted-foreground">None (root term)</span>
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="p-0 w-[--radix-popover-trigger-width]" align="start">
                  <Command>
                    <CommandInput
                      placeholder="Search parent term..."
                      value={parentSearch}
                      onValueChange={setParentSearch}
                    />
                    <CommandList>
                      <CommandEmpty>No matching terms</CommandEmpty>
                      <CommandGroup>
                        <CommandItem
                          value="__none__"
                          onSelect={() => {
                            setParentId("none")
                            setParentPopoverOpen(false)
                            setParentSearch("")
                          }}
                        >
                          <span className="text-muted-foreground">None (root term)</span>
                        </CommandItem>
                        {terms.map((t) => (
                          <CommandItem
                            key={t.id}
                            value={t.name}
                            onSelect={() => {
                              setParentId(String(t.id))
                              setParentPopoverOpen(false)
                              setParentSearch("")
                            }}
                          >
                            <div className="flex flex-col">
                              <span>{t.name}</span>
                              {t.source && (
                                <span className="text-xs text-muted-foreground">
                                  {t.source}
                                </span>
                              )}
                            </div>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={saving}>
                Cancel
              </Button>
            </DialogClose>
            <Button onClick={handleCreate} disabled={saving || !name.trim()}>
              {saving ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Delete Confirm Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Terms</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete {selectedIds.size} glossary term
              {selectedIds.size !== 1 ? "s" : ""}? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={deleting}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant="destructive"
              onClick={handleBulkDelete}
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
