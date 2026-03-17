"use client"

import { useState } from "react"
import { Plus, X, Pencil, Check } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { useNotes } from "./notes-provider"

export function SectionTabs() {
  const { sections, currentSection, selectSection, addSection, removeSection } = useNotes()
  const [adding, setAdding] = useState(false)
  const [newTitle, setNewTitle] = useState("")

  const handleAdd = async () => {
    if (!newTitle.trim()) {
      setAdding(false)
      return
    }
    await addSection(newTitle.trim())
    setNewTitle("")
    setAdding(false)
  }

  return (
    <div className="flex items-center gap-1 px-2 py-1.5 border-b overflow-x-auto shrink-0">
      {sections.map((sec) => (
        <button
          key={sec.id}
          onClick={() => selectSection(sec)}
          className={`group flex items-center gap-1 px-3 py-1.5 rounded-md text-base whitespace-nowrap transition-colors ${
            currentSection?.id === sec.id
              ? "bg-primary text-primary-foreground"
              : "hover:bg-muted text-muted-foreground"
          }`}
        >
          {sec.title}
          {sections.length > 1 && (
            <X
              className={`h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity ${
                currentSection?.id === sec.id ? "text-primary-foreground" : "text-muted-foreground"
              }`}
              onClick={(e) => {
                e.stopPropagation()
                removeSection(sec.id)
              }}
            />
          )}
        </button>
      ))}

      {adding ? (
        <div className="flex items-center gap-1">
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
            placeholder="Section name"
            className="h-7 w-32 text-sm"
          />
        </div>
      ) : (
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={() => setAdding(true)}
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  )
}
