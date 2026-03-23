"use client"

import { useCallback, useContext, useEffect, useMemo, useRef, useState, createContext } from "react"
import {
  BookOpen, ChevronRight, FolderOpen, FileText, Plus, Pencil, Trash2, Check, X,
} from "lucide-react"
import { AgGridReact } from "ag-grid-react"
import { AllCommunityModule, ModuleRegistry, type ColDef, type CellValueChangedEvent } from "ag-grid-community"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Textarea } from "@workspace/ui/components/textarea"
import {
  Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@workspace/ui/components/command"
import { Popover, PopoverContent, PopoverTrigger } from "@workspace/ui/components/popover"
import { DashboardHeader } from "@/components/dashboard-header"
import {
  createGlossaryTerm, deleteGlossaryTerm, fetchGlossaryTerms, updateGlossaryTerm,
} from "@/features/glossary/api"
import type { GlossaryTerm } from "@/features/datasets/data/schema"
import { useAuth } from "@/features/auth"

ModuleRegistry.registerModules([AllCommunityModule])

// ---------------------------------------------------------------------------
// Tree node type
// ---------------------------------------------------------------------------
type TreeNode = GlossaryTerm & { children: TreeNode[]; depth: number }

function buildTree(terms: GlossaryTerm[]): TreeNode[] {
  const map = new Map<number, TreeNode>()
  const roots: TreeNode[] = []
  for (const t of terms) map.set(t.id, { ...t, children: [], depth: 0 })
  for (const node of map.values()) {
    if (node.parent_id && map.has(node.parent_id)) {
      const parent = map.get(node.parent_id)!
      node.depth = parent.depth + 1
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  }
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name))
    for (const n of nodes) sortNodes(n.children)
  }
  sortNodes(roots)
  return roots
}

// Collect all descendant IDs (including self)
function collectIds(node: TreeNode): number[] {
  const ids = [node.id]
  for (const c of node.children) ids.push(...collectIds(c))
  return ids
}

// ---------------------------------------------------------------------------
// Delete renderer for AG Grid
// ---------------------------------------------------------------------------
const TermDeleteCtx = createContext<(id: number) => void>(() => {})
function TermDeleteRenderer(props: { value: number }) {
  const onDelete = useContext(TermDeleteCtx)
  return (
    <button type="button" onClick={() => onDelete(props.value)}
      className="flex items-center justify-center w-full h-full text-muted-foreground hover:text-destructive transition-colors cursor-pointer">
      <Trash2 className="h-3.5 w-3.5" />
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function GlossaryPage() {
  const { user } = useAuth()
  const [terms, setTerms] = useState<GlossaryTerm[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  // Category editing
  const [editingNodeId, setEditingNodeId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState("")

  // Add dialog
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [addMode, setAddMode] = useState<"category" | "term">("term")
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")
  const [newSource, setNewSource] = useState("")

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      setTerms(await fetchGlossaryTerms())
    } catch { /* */ } finally {
      setIsLoading(false)
    }
  }, [])
  useEffect(() => { load() }, [load])

  // Tree
  const tree = useMemo(() => buildTree(terms), [terms])
  const nodeMap = useMemo(() => {
    const m = new Map<number, TreeNode>()
    const walk = (nodes: TreeNode[]) => { for (const n of nodes) { m.set(n.id, n); walk(n.children) } }
    walk(tree)
    return m
  }, [tree])

  // Selected node
  const selectedNode = selectedNodeId ? nodeMap.get(selectedNodeId) ?? null : null
  const isCategory = selectedNode ? selectedNode.children.length > 0 : false

  // Terms to show in right panel: leaf terms under selected node (or all leaves if none selected)
  const rightTerms = useMemo(() => {
    if (!selectedNode) {
      // Show all leaf terms (no children)
      return terms.filter(t => {
        const node = nodeMap.get(t.id)
        return node ? node.children.length === 0 : true
      })
    }
    // Show leaf descendants of selected node
    const allIds = new Set(collectIds(selectedNode))
    return terms.filter(t => {
      if (!allIds.has(t.id)) return false
      const node = nodeMap.get(t.id)
      return node ? node.children.length === 0 : true
    })
  }, [selectedNode, terms, nodeMap])

  // Unique sources
  const sources = useMemo(() =>
    Array.from(new Set(terms.map(t => t.source).filter(Boolean) as string[])).sort(),
  [terms])

  // Tree toggle
  const toggleExpand = (id: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  // Category CRUD
  const addCategory = () => {
    setAddMode("category")
    setNewName("")
    setNewDesc("")
    setNewSource("")
    setAddDialogOpen(true)
  }

  const addTerm = () => {
    setAddMode("term")
    setNewName("")
    setNewDesc("")
    setNewSource("")
    setAddDialogOpen(true)
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    await createGlossaryTerm({
      name: newName.trim(),
      description: newDesc.trim() || undefined,
      source: newSource.trim() || undefined,
      parent_id: selectedNodeId ?? undefined,
    })
    setAddDialogOpen(false)
    await load()
  }

  const startRename = (id: number, name: string) => {
    setEditingNodeId(id)
    setEditingName(name)
  }

  const saveRename = async () => {
    if (!editingNodeId || !editingName.trim()) return
    await updateGlossaryTerm(editingNodeId, { name: editingName.trim() })
    setEditingNodeId(null)
    await load()
  }

  const cancelRename = () => setEditingNodeId(null)

  const deleteNode = async (id: number) => {
    await deleteGlossaryTerm(id)
    if (selectedNodeId === id) setSelectedNodeId(null)
    await load()
  }

  // AG Grid — term update
  const onCellValueChanged = useCallback(async (event: CellValueChangedEvent) => {
    const { data, colDef, newValue, oldValue } = event
    if (newValue === oldValue) return
    const field = colDef.field
    if (!field || !data.id) return
    await updateGlossaryTerm(data.id, { [field]: newValue })
  }, [])

  const deleteTermFromGrid = useCallback(async (id: number) => {
    await deleteGlossaryTerm(id)
    load()
  }, [load])

  const columnDefs = useMemo<ColDef[]>(() => [
    { headerName: "#", valueGetter: (p) => (p.node?.rowIndex ?? 0) + 1, width: 50, maxWidth: 55, editable: false, sortable: false, cellStyle: { color: "#9ca3af", textAlign: "right" } },
    { headerName: "Name", field: "name", minWidth: 160, editable: true, cellStyle: { fontWeight: 500 } },
    { headerName: "Description", field: "description", flex: 1, minWidth: 200, editable: true },
    { headerName: "Source", field: "source", width: 130, editable: true },
    { headerName: "", field: "id", width: 45, maxWidth: 45, editable: false, sortable: false, cellRenderer: "deleteRenderer" },
  ], [])

  const components = useMemo(() => ({ deleteRenderer: TermDeleteRenderer }), [])

  // Visible tree nodes
  const visibleNodes = useMemo(() => {
    const result: TreeNode[] = []
    const walk = (nodes: TreeNode[]) => {
      for (const n of nodes) {
        result.push(n)
        if (n.children.length > 0 && expandedIds.has(n.id)) walk(n.children)
      }
    }
    walk(tree)
    return result
  }, [tree, expandedIds])

  // Breadcrumb
  const breadcrumb = useMemo(() => {
    if (!selectedNode) return "All Terms"
    const parts: string[] = []
    let current: TreeNode | undefined = selectedNode
    while (current) {
      parts.unshift(current.name)
      current = current.parent_id ? nodeMap.get(current.parent_id) : undefined
    }
    return parts.join(" / ")
  }, [selectedNode, nodeMap])

  return (
    <TermDeleteCtx.Provider value={deleteTermFromGrid}>
    <>
      <DashboardHeader title="Business Glossary" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex flex-1 gap-4 min-h-0">

          {/* ========== Left: Tree ========== */}
          <div className="flex flex-col w-72 min-w-[260px] min-h-0 border rounded-lg">
            <div className="flex items-center justify-between px-3 py-2 border-b flex-shrink-0">
              <span className="text-sm font-medium">Classification</span>
              {user?.is_admin && (
                <Button variant="outline" size="sm" onClick={addCategory}>
                  <Plus className="h-3.5 w-3.5 mr-1" />Add
                </Button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto py-1">
              {/* "All" root item */}
              <button
                type="button"
                onClick={() => setSelectedNodeId(null)}
                className={`w-full text-left flex items-center gap-2 px-3 py-1.5 text-sm transition-colors ${
                  selectedNodeId === null ? "bg-primary/10 text-primary font-medium" : "hover:bg-muted/50"
                }`}
              >
                <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                All Terms
                <span className="ml-auto text-xs text-muted-foreground">
                  {terms.filter(t => { const n = nodeMap.get(t.id); return n ? n.children.length === 0 : true }).length}
                </span>
              </button>

              {/* Tree nodes */}
              {visibleNodes.map(node => {
                const hasChildren = node.children.length > 0
                const isExpanded = expandedIds.has(node.id)
                const isSelected = selectedNodeId === node.id
                const isEditing = editingNodeId === node.id
                const leafCount = collectIds(node).filter(id => {
                  const n = nodeMap.get(id)
                  return n ? n.children.length === 0 : false
                }).length

                return (
                  <div
                    key={node.id}
                    className={`flex items-center gap-1 pr-1 transition-colors group ${
                      isSelected ? "bg-primary/10" : "hover:bg-muted/50"
                    }`}
                    style={{ paddingLeft: `${node.depth * 16 + 8}px` }}
                  >
                    {/* Expand toggle */}
                    <button
                      type="button"
                      className={`shrink-0 p-0.5 rounded hover:bg-muted ${hasChildren ? "cursor-pointer" : "invisible"}`}
                      onClick={(e) => { e.stopPropagation(); if (hasChildren) toggleExpand(node.id) }}
                    >
                      <ChevronRight className={`h-3.5 w-3.5 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                    </button>

                    {/* Icon */}
                    {hasChildren
                      ? <FolderOpen className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                      : <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    }

                    {/* Name (editable) */}
                    {isEditing ? (
                      <div className="flex items-center gap-1 flex-1 min-w-0">
                        <Input
                          value={editingName}
                          onChange={e => setEditingName(e.target.value)}
                          onKeyDown={e => { if (e.key === "Enter") saveRename(); if (e.key === "Escape") cancelRename() }}
                          className="h-6 text-xs px-1 flex-1"
                          autoFocus
                        />
                        <button type="button" onClick={saveRename} className="text-green-600 hover:text-green-800">
                          <Check className="h-3.5 w-3.5" />
                        </button>
                        <button type="button" onClick={cancelRename} className="text-muted-foreground hover:text-foreground">
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setSelectedNodeId(node.id)}
                        className={`flex-1 min-w-0 text-left truncate text-sm py-1 ${isSelected ? "text-primary font-medium" : ""}`}
                      >
                        {node.name}
                      </button>
                    )}

                    {/* Count */}
                    {!isEditing && hasChildren && (
                      <span className="text-xs text-muted-foreground shrink-0">{leafCount}</span>
                    )}

                    {/* Actions (visible on hover) */}
                    {!isEditing && user?.is_admin && (
                      <div className="shrink-0 flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <button type="button" onClick={(e) => { e.stopPropagation(); startRename(node.id, node.name) }}
                          className="p-0.5 text-muted-foreground hover:text-foreground">
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button type="button" onClick={(e) => { e.stopPropagation(); deleteNode(node.id) }}
                          className="p-0.5 text-muted-foreground hover:text-destructive">
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* ========== Right: Term List (AG Grid) ========== */}
          <div className="flex flex-col flex-1 min-h-0">
            <div className="flex items-center justify-between mb-2 flex-shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{breadcrumb}</span>
                <span className="text-sm text-muted-foreground">({rightTerms.length})</span>
              </div>
              {user?.is_admin && (
                <Button variant="outline" size="sm" onClick={addTerm}>
                  <Plus className="h-3.5 w-3.5 mr-1" />Add Term
                </Button>
              )}
            </div>
            <div className="ag-theme-alpine flex-1 min-h-0" style={{
              "--ag-font-family": "var(--font-d2coding), 'D2Coding', Consolas, monospace",
              "--ag-font-size": "13px",
            } as React.CSSProperties}>
              <AgGridReact
                columnDefs={columnDefs}
                rowData={rightTerms}
                defaultColDef={{ resizable: true, sortable: true, filter: false, minWidth: 50 }}
                headerHeight={32}
                rowHeight={30}
                stopEditingWhenCellsLoseFocus
                onCellValueChanged={onCellValueChanged}
                animateRows={false}
                getRowId={(params) => String(params.data.id)}
                components={components}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ========== Add Dialog ========== */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {addMode === "category" ? "Add Category" : "Add Term"}
            </DialogTitle>
            <DialogDescription>
              {addMode === "category"
                ? `Create a new category${selectedNode ? ` under "${selectedNode.name}"` : ""}.`
                : `Add a term${selectedNode ? ` under "${selectedNode.name}"` : ""}.`
              }
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>Name</Label>
              <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder={addMode === "category" ? "e.g. 고객 관리" : "e.g. 고객 생애 가치"} />
            </div>
            <div className="grid gap-2">
              <Label>Description</Label>
              <Textarea value={newDesc} onChange={e => setNewDesc(e.target.value)} rows={3} placeholder="Define this term..." />
            </div>
            {addMode === "term" && (
              <div className="grid gap-2">
                <Label>Source</Label>
                <Input value={newSource} onChange={e => setNewSource(e.target.value)} placeholder="e.g. 마케팅팀" />
              </div>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button onClick={handleCreate} disabled={!newName.trim()}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
    </TermDeleteCtx.Provider>
  )
}
