"use client"

import { ConfirmDialog } from "@/components/confirm-dialog"

type DeleteDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  selectedPaths: string[]
  onConfirm: () => void
  isLoading?: boolean
}

export function DeleteDialog({
  open,
  onOpenChange,
  selectedPaths,
  onConfirm,
  isLoading,
}: DeleteDialogProps) {
  const count = selectedPaths.length
  const folderCount = selectedPaths.filter((k) => k.endsWith("/")).length
  const fileCount = count - folderCount

  const parts: string[] = []
  if (fileCount > 0) parts.push(`${fileCount} file${fileCount > 1 ? "s" : ""}`)
  if (folderCount > 0) parts.push(`${folderCount} folder${folderCount > 1 ? "s" : ""}`)
  const summary = parts.join(" and ")

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Delete"
      desc={
        <span>
          Are you sure you want to delete {summary}?
          {folderCount > 0 && (
            <span className="block mt-1 text-xs text-destructive">
              Deleting a folder will remove all files and subdirectories under it.
            </span>
          )}
          <span className="block mt-2 text-xs text-muted-foreground">
            This action cannot be undone.
          </span>
        </span>
      }
      destructive
      confirmText={isLoading ? "Deleting..." : "Delete"}
      handleConfirm={onConfirm}
      isLoading={isLoading}
    />
  )
}
