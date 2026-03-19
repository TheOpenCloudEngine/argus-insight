"use client"

import { useState } from "react"
import { Loader2, TriangleAlert } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  catalogName: string
  onConfirm: () => Promise<void>
}

export function UCDeleteCatalogDialog({ open, onOpenChange, catalogName, onConfirm }: Props) {
  const [confirmation, setConfirmation] = useState("")
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const expected = `DELETE ${catalogName}`
  const isMatch = confirmation === expected

  function handleOpenChange(next: boolean) {
    if (!next) {
      setConfirmation("")
      setError(null)
    }
    onOpenChange(next)
  }

  async function handleDelete() {
    if (!isMatch) return
    setDeleting(true)
    setError(null)
    try {
      await onConfirm()
      handleOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete catalog")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <TriangleAlert className="h-5 w-5 text-destructive" />
            Delete Catalog
          </AlertDialogTitle>
          <AlertDialogDescription className="space-y-3">
            <span className="block">
              Deleting a catalog is irreversible. Please proceed with caution.
            </span>
            <span className="block font-medium text-foreground">
              To confirm, type <code className="rounded bg-muted px-1.5 py-0.5 text-destructive font-mono text-sm">{expected}</code> below.
            </span>
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-2">
          <Label htmlFor="delete-confirmation" className="sr-only">Confirmation</Label>
          <Input
            id="delete-confirmation"
            placeholder={expected}
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
        </div>

        {error && (
          <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}

        <AlertDialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={!isMatch || deleting}>
            {deleting && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
            Delete
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
