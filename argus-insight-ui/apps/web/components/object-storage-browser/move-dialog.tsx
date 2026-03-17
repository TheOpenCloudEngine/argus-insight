"use client"

import { useState } from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

type MoveDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentKey: string
  onConfirm: (destinationKey: string) => Promise<void>
  isLoading: boolean
}

export function MoveDialog({
  open,
  onOpenChange,
  currentKey,
  onConfirm,
  isLoading,
}: MoveDialogProps) {
  const [destination, setDestination] = useState(currentKey)
  const [error, setError] = useState("")

  function handleOpenChange(v: boolean) {
    if (v) {
      setDestination(currentKey)
      setError("")
    }
    onOpenChange(v)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = destination.trim()
    if (!trimmed) {
      setError("Destination path cannot be empty.")
      return
    }
    if (trimmed === currentKey) {
      setError("Destination is the same as the current path.")
      return
    }
    setError("")
    await onConfirm(trimmed)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Move</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-4">
            <div>
              <Label className="text-sm font-medium">Current path</Label>
              <p className="text-sm mt-1 font-mono bg-muted px-2 py-1 rounded break-all">
                {currentKey}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="move-input">Destination path</Label>
              <Input
                id="move-input"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                autoFocus
                disabled={isLoading}
                className="font-mono"
              />
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              Move
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
