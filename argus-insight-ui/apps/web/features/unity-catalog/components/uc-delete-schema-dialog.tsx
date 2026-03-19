"use client"

import { useState } from "react"
import { Loader2, TriangleAlert } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import type { Schema } from "../data/schema"

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  schemas: Schema[]
  onConfirm: (schemaFullName: string) => Promise<void>
}

export function UCDeleteSchemaDialog({ open, onOpenChange, schemas, onConfirm }: Props) {
  const [selected, setSelected] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const deletableSchemas = schemas.filter((s) => s.name !== "default")
  const expected = selected ? `DELETE ${selected}` : ""
  const isMatch = !!selected && confirmation === expected

  function handleOpenChange(next: boolean) {
    if (!next) {
      setSelected("")
      setConfirmation("")
      setError(null)
    }
    onOpenChange(next)
  }

  function handleSelectSchema(value: string) {
    setSelected(value)
    setConfirmation("")
    setError(null)
  }

  async function handleDelete() {
    if (!isMatch) return
    const schema = deletableSchemas.find((s) => s.name === selected)
    if (!schema) return

    setDeleting(true)
    setError(null)
    try {
      await onConfirm(schema.full_name)
      handleOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete schema")
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
            Delete Schema
          </AlertDialogTitle>
          <AlertDialogDescription>
            Deleting a schema is irreversible. Please proceed with caution.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Select schema to delete</Label>
            <Select value={selected} onValueChange={handleSelectSchema}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a schema..." />
              </SelectTrigger>
              <SelectContent>
                {deletableSchemas.map((s) => (
                  <SelectItem key={s.name} value={s.name}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selected && (
            <div className="space-y-2">
              <Label htmlFor="delete-confirmation">
                To confirm, type{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 text-destructive font-mono text-sm">
                  {expected}
                </code>
              </Label>
              <Input
                id="delete-confirmation"
                placeholder={expected}
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
          )}
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
