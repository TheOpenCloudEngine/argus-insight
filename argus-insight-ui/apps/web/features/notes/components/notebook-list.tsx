"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { useRouter } from "next/navigation"
import {
  BookOpen,
  Plus,
  Search,
  Trash2,
  Pin,
  MoreVertical,
  Palette,
} from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Card } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@workspace/ui/components/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { useNotes } from "./notes-provider"

const COLORS: Record<string, string> = {
  default: "bg-muted",
  blue: "bg-blue-100",
  green: "bg-green-100",
  red: "bg-red-100",
  purple: "bg-purple-100",
  orange: "bg-orange-100",
}

const COLOR_LABELS: Record<string, string> = {
  default: "Default",
  blue: "Blue",
  green: "Green",
  red: "Red",
  purple: "Purple",
  orange: "Orange",
}

export function NotebookList() {
  const router = useRouter()
  const { notebooks, loadNotebooks, createNotebook, changeNotebookColor, removeNotebook } = useNotes()
  const [search, setSearch] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [newTitle, setNewTitle] = useState("")
  const [newDescription, setNewDescription] = useState("")
  const [newColor, setNewColor] = useState("default")
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const doSearch = useCallback(
    (value: string) => {
      loadNotebooks(value || undefined)
    },
    [loadNotebooks],
  )

  const handleSearchChange = (value: string) => {
    setSearch(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(value), 3000)
  }

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      doSearch(search)
    }
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const handleCreate = async () => {
    if (!newTitle.trim()) return
    const nb = await createNotebook(newTitle.trim(), newDescription.trim() || undefined, newColor)
    setDialogOpen(false)
    setNewTitle("")
    setNewDescription("")
    setNewColor("default")
    router.push(`/dashboard/notes/${nb.id}`)
  }

  const handleColorChange = async (e: React.MouseEvent, id: number, color: string) => {
    e.stopPropagation()
    await changeNotebookColor(id, color)
  }

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    await removeNotebook(id)
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search notebooks..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            className="pl-8 h-9"
          />
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-1" />
              New Notebook
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Notebook</DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-3 py-4">
              <Input
                placeholder="Notebook title"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              />
              <Input
                placeholder="Description (optional)"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
              />
              <div className="flex gap-2">
                {Object.keys(COLORS).map((c) => (
                  <button
                    key={c}
                    onClick={() => setNewColor(c)}
                    className={`h-6 w-6 rounded-full border-2 ${COLORS[c]} ${
                      newColor === c ? "border-primary" : "border-transparent"
                    }`}
                  />
                ))}
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={!newTitle.trim()}>
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {notebooks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <BookOpen className="h-12 w-12 mb-4" />
          <p className="text-lg font-medium">No notebooks yet</p>
          <p className="text-sm">Create your first notebook to get started</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5">
          {notebooks.map((nb) => (
            <Card
              key={nb.id}
              className={`cursor-pointer hover:shadow-md transition-shadow relative group ${COLORS[nb.color] || COLORS.default}`}
              onClick={() => router.push(`/dashboard/notes/${nb.id}`)}
            >
              <div className="px-3 py-2.5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-1.5 min-w-0">
                    {nb.isPinned && <Pin className="h-3 w-3 text-muted-foreground shrink-0" />}
                    <h3 className="text-lg font-semibold truncate">{nb.title}</h3>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 opacity-0 group-hover:opacity-100 shrink-0"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreVertical className="h-3 w-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger onClick={(e) => e.stopPropagation()}>
                          <Palette className="h-4 w-4 mr-2" />
                          Color
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent>
                          {Object.keys(COLORS).map((c) => (
                            <DropdownMenuItem
                              key={c}
                              onClick={(e) => handleColorChange(e, nb.id, c)}
                            >
                              <span className={`h-3 w-3 rounded-full ${COLORS[c]} border border-border mr-2 inline-block`} />
                              {COLOR_LABELS[c]}
                              {nb.color === c && <span className="ml-auto text-muted-foreground">✓</span>}
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={(e) => handleDelete(e, nb.id)}
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                {nb.description && (
                  <p className="text-base text-muted-foreground mt-0.5 truncate">
                    {nb.description}
                  </p>
                )}
                <div className="flex items-center gap-3 mt-2 text-sm text-muted-foreground">
                  <span>{nb.sectionCount} sections</span>
                  <span>{nb.pageCount} pages</span>
                </div>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Updated {new Date(nb.updatedAt).toLocaleDateString()}
                </p>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
