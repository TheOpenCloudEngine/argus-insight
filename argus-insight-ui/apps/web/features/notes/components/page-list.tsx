"use client"

import { useState } from "react"
import { Plus, FileText, Pin, Trash2 } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { useNotes } from "./notes-provider"

export function PageList() {
  const { pages, currentPage, selectPage, addPage, removePage } = useNotes()
  const [adding, setAdding] = useState(false)
  const [newTitle, setNewTitle] = useState("")

  const handleAdd = async () => {
    if (!newTitle.trim()) {
      setAdding(false)
      return
    }
    await addPage(newTitle.trim())
    setNewTitle("")
    setAdding(false)
  }

  return (
    <div className="flex flex-col h-full border-r w-56 shrink-0">
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <span className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Pages
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => setAdding(true)}
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>

      {adding && (
        <div className="p-2 border-b">
          <Input
            autoFocus
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd()
              if (e.key === "Escape") {
                setAdding(false)
                setNewTitle("")
              }
            }}
            onBlur={handleAdd}
            placeholder="Page title"
            className="h-7 text-sm"
          />
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {pages.length === 0 && !adding ? (
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <FileText className="h-8 w-8 mb-2" />
            <p className="text-sm">No pages yet</p>
          </div>
        ) : (
          pages.map((page) => (
            <button
              key={page.id}
              onClick={() => selectPage(page.id)}
              className={`group w-full text-left px-3 py-2 border-b hover:bg-muted/50 transition-colors ${
                currentPage?.id === page.id ? "bg-muted" : ""
              }`}
            >
              <div className="flex items-center gap-1.5">
                {page.isPinned && <Pin className="h-3 w-3 text-muted-foreground shrink-0" />}
                <span className="text-base truncate">{page.title}</span>
                <Trash2
                  className="h-3 w-3 ml-auto text-muted-foreground opacity-0 group-hover:opacity-100 shrink-0 hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation()
                    removePage(page.id)
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">
                {new Date(page.updatedAt).toLocaleDateString()}
              </p>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
