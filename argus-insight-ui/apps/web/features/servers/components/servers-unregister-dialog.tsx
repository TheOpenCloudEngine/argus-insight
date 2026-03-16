"use client"

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { Button } from "@workspace/ui/components/button"
import { unregisterServers } from "../api"
import { type Server } from "../data/schema"
import { useServers } from "./servers-provider"

type ServersUnregisterDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Single server from row action, or null for bulk action */
  currentRow: Server | null
  selectedServers: Server[]
}

export function ServersUnregisterDialog({
  open,
  onOpenChange,
  currentRow,
  selectedServers,
}: ServersUnregisterDialogProps) {
  const { refreshServers } = useServers()

  // Determine targets: single row action vs bulk action
  const targets = currentRow ? [currentRow] : selectedServers
  const registered = targets.filter((s) => s.status === "REGISTERED")
  const isBulk = !currentRow
  const hasNoSelection = isBulk && targets.length === 0

  const handleConfirm = async () => {
    if (registered.length === 0) {
      onOpenChange(false)
      return
    }
    try {
      await unregisterServers(registered.map((s) => s.hostname))
      await refreshServers()
    } catch (err) {
      console.error("Failed to unregister servers:", err)
    }
    onOpenChange(false)
  }

  // Case 1: Bulk action but nothing selected
  if (hasNoSelection) {
    return (
      <AlertDialog open={open} onOpenChange={onOpenChange}>
        <AlertDialogContent>
          <AlertDialogHeader className="text-start">
            <AlertDialogTitle>Remove From Manager</AlertDialogTitle>
            <AlertDialogDescription>
              Please select servers to unregister.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button onClick={() => onOpenChange(false)}>OK</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    )
  }

  // Case 2: Confirm unregistration
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader className="text-start">
          <AlertDialogTitle>Remove From Manager</AlertDialogTitle>
          <AlertDialogDescription>
            {registered.length > 0
              ? `Are you sure you want to unregister ${registered.length} server(s)?`
              : "No registered servers in the selection."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-row justify-end gap-2 sm:flex-row">
          {registered.length > 0 ? (
            <>
              <Button onClick={handleConfirm}>Yes</Button>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                No
              </Button>
            </>
          ) : (
            <Button onClick={() => onOpenChange(false)}>OK</Button>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
