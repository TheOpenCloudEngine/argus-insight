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
  /** Set of all existing folder keys (ending with "/"). */
  existingFolderKeys: Set<string>
  /** Set of all existing object keys (files). */
  existingObjectKeys: Set<string>
  onConfirm: (destinationKey: string) => Promise<void>
  isLoading: boolean
}

export function MoveDialog({
  open,
  onOpenChange,
  currentKey,
  existingFolderKeys,
  existingObjectKeys,
  onConfirm,
  isLoading,
}: MoveDialogProps) {
  const [destination, setDestination] = useState(currentKey)
  const [error, setError] = useState("")
  const [checked, setChecked] = useState(false)

  function handleOpenChange(v: boolean) {
    if (v) {
      setDestination(currentKey)
      setError("")
      setChecked(false)
    }
    onOpenChange(v)
  }

  /** Extract the file/folder name from the current key. */
  function getSourceName(): string {
    const isFolder = currentKey.endsWith("/")
    const key = isFolder ? currentKey.slice(0, -1) : currentKey
    const lastSlash = key.lastIndexOf("/")
    const name = lastSlash >= 0 ? key.substring(lastSlash + 1) : key
    return isFolder ? name + "/" : name
  }

  /**
   * Resolve the final destination key.
   * - If the destination is an existing folder, move into it.
   * - Otherwise use the destination as-is.
   */
  function resolveDestination(trimmed: string): string {
    if (existingFolderKeys.has(trimmed) || existingFolderKeys.has(trimmed + "/")) {
      const folder = trimmed.endsWith("/") ? trimmed : trimmed + "/"
      return folder + getSourceName()
    }
    return trimmed
  }

  function handleCheck() {
    const trimmed = destination.trim()
    if (!trimmed) {
      setError("Destination path cannot be empty.")
      return
    }
    if (trimmed === currentKey) {
      setError("Destination is the same as the current path.")
      return
    }
    const resolved = resolveDestination(trimmed)
    if (resolved === currentKey) {
      setError("Destination is the same as the current path.")
      return
    }
    if (existingObjectKeys.has(resolved)) {
      setError("해당 위치에 Object가 존재합니다.")
      return
    }
    setError("")
    setChecked(true)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = destination.trim()
    const resolved = resolveDestination(trimmed)
    await onConfirm(resolved)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Move</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-4">
            <p className="text-xs text-destructive">
              Destination Path로 지정한 위치에 같은 Object가 존재하는 경우 Overwrite할 수 있습니다.
            </p>
            <div>
              <Label className="text-sm font-medium">Current path</Label>
              <p className="text-sm mt-1 font-mono bg-muted px-2 py-1 rounded break-all">
                {currentKey}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="move-input">Destination path</Label>
              <div className="flex gap-2">
                <Input
                  id="move-input"
                  value={destination}
                  onChange={(e) => {
                    setDestination(e.target.value)
                    setError("")
                    setChecked(false)
                  }}
                  autoFocus
                  disabled={isLoading}
                  className="font-mono flex-1"
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleCheck}
                  disabled={isLoading || checked}
                  className="shrink-0"
                >
                  Check
                </Button>
              </div>
              {error && <p className="text-xs text-destructive">{error}</p>}
            </div>
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
            <Button type="submit" disabled={isLoading || !checked}>
              {isLoading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              Move
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
