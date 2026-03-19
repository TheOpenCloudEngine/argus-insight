"use client"

import { useState } from "react"
import { Pencil, Plus } from "lucide-react"
import { Button } from "@workspace/ui/components/button"

type UCDescriptionBoxProps = {
  comment: string | null | undefined
  onEdit?: (comment: string) => void
}

export function UCDescriptionBox({ comment, onEdit }: UCDescriptionBoxProps) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(comment ?? "")

  function handleSave() {
    onEdit?.(value)
    setEditing(false)
  }

  function handleCancel() {
    setValue(comment ?? "")
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Description</h4>
        <textarea
          className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
          rows={3}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoFocus
        />
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave}>Save</Button>
          <Button size="sm" variant="outline" onClick={handleCancel}>Cancel</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-semibold">Description</h4>
        {comment && onEdit && (
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setEditing(true)}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      {comment ? (
        <p className="text-muted-foreground text-sm">{comment}</p>
      ) : onEdit ? (
        <Button variant="link" size="sm" className="h-auto p-0 text-sm" onClick={() => setEditing(true)}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Add description
        </Button>
      ) : (
        <p className="text-muted-foreground text-sm italic">No description</p>
      )}
    </div>
  )
}
