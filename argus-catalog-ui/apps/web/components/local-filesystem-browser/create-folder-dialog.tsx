"use client"

import { useState } from "react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

type CreateFolderDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentPath: string
  onConfirm: (folderName: string) => void
  isLoading?: boolean
}

const FOLDER_NAME_REGEX = /^[a-zA-Z0-9_\-.]+$/

export function CreateFolderDialog({
  open,
  onOpenChange,
  currentPath,
  onConfirm,
  isLoading,
}: CreateFolderDialogProps) {
  const [name, setName] = useState("")
  const [error, setError] = useState("")

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const trimmed = name.trim()
    if (!trimmed) {
      setError("Folder name is required.")
      return
    }
    if (!FOLDER_NAME_REGEX.test(trimmed)) {
      setError("Only letters, numbers, hyphens, underscores, and dots are allowed.")
      return
    }

    onConfirm(trimmed)
    setName("")
    setError("")
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      setName("")
      setError("")
    }
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[420px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Folder</DialogTitle>
            <DialogDescription>
              Create a new folder under{" "}
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                {currentPath}
              </code>
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 py-4">
            <Label htmlFor="folder-name">Folder name</Label>
            <Input
              id="folder-name"
              placeholder="my-folder"
              value={name}
              onChange={(e) => {
                setName(e.target.value)
                if (error) setError("")
              }}
              autoFocus
            />
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
