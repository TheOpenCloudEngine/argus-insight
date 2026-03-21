"use client"

import { useCallback, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { hardDeleteModels } from "../api"
import { useModels } from "./models-provider"

const CONFIRM_TEXT = "DELETE MODELS"

export function ModelsDeleteDialog() {
  const { open, setOpen, deleteTargetNames, refreshModels, clearSelection } = useModels()
  const [confirmInput, setConfirmInput] = useState("")
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isConfirmed = confirmInput === CONFIRM_TEXT
  const count = deleteTargetNames.length

  const handleDelete = useCallback(async () => {
    if (!isConfirmed || count === 0) return
    setDeleting(true)
    setError(null)
    try {
      await hardDeleteModels(deleteTargetNames)
      setConfirmInput("")
      setOpen(null)
      clearSelection()
      await refreshModels()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete models")
    } finally {
      setDeleting(false)
    }
  }, [isConfirmed, count, deleteTargetNames, setOpen, clearSelection, refreshModels])

  function handleOpenChange(v: boolean) {
    if (!v) {
      setConfirmInput("")
      setError(null)
    }
    if (!v) setOpen(null)
  }

  return (
    <Dialog open={open === "delete"} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete Models</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <p className="text-sm">
            You have selected <strong>{count}</strong> model{count > 1 ? "s" : ""}.
            Are you sure you want to delete? Deletion cannot be undone.
          </p>

          <div className="rounded-md border p-3 max-h-32 overflow-y-auto">
            <ul className="text-sm text-muted-foreground space-y-1">
              {deleteTargetNames.map((name) => (
                <li key={name} className="truncate">{name}</li>
              ))}
            </ul>
          </div>

          <div className="grid gap-2">
            <p className="text-sm text-muted-foreground">
              Type <strong>{CONFIRM_TEXT}</strong> to confirm:
            </p>
            <Input
              value={confirmInput}
              onChange={(e) => setConfirmInput(e.target.value)}
              placeholder={CONFIRM_TEXT}
              disabled={deleting}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={!isConfirmed || deleting}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
