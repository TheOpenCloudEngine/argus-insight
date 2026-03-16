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
import { registerServers } from "../api"
import { type Server } from "../data/schema"
import { useServers } from "./servers-provider"

type ServersRegisterDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Single server from row action, or null for bulk action */
  currentRow: Server | null
  selectedServers: Server[]
}

export function ServersRegisterDialog({
  open,
  onOpenChange,
  currentRow,
  selectedServers,
}: ServersRegisterDialogProps) {
  const { refreshServers } = useServers()

  // Determine targets: single row action vs bulk action
  const targets = currentRow ? [currentRow] : selectedServers
  const unregistered = targets.filter((s) => s.status === "UNREGISTERED")
  const isBulk = !currentRow
  const hasNoSelection = isBulk && targets.length === 0

  const handleConfirm = async () => {
    if (unregistered.length === 0) {
      onOpenChange(false)
      return
    }
    try {
      await registerServers(unregistered.map((s) => s.hostname))
      await refreshServers()
    } catch (err) {
      console.error("Failed to register servers:", err)
    }
    onOpenChange(false)
  }

  // Case 1: Bulk action but nothing selected
  if (hasNoSelection) {
    return (
      <AlertDialog open={open} onOpenChange={onOpenChange}>
        <AlertDialogContent>
          <AlertDialogHeader className="text-start">
            <AlertDialogTitle>Register Servers</AlertDialogTitle>
            <AlertDialogDescription>
              Please select servers to register.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button onClick={() => onOpenChange(false)}>OK</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    )
  }

  // Case 2: Confirm registration
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader className="text-start">
          <AlertDialogTitle>Register Servers</AlertDialogTitle>
          <AlertDialogDescription>
            {unregistered.length > 0
              ? `Are you sure you want to register ${unregistered.length} server(s)?`
              : "No unregistered servers in the selection."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-row justify-end gap-2 sm:flex-row">
          {unregistered.length > 0 ? (
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
