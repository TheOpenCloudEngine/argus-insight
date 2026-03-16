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

type ServersTerminalWarningDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ServersTerminalWarningDialog({
  open,
  onOpenChange,
}: ServersTerminalWarningDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader className="text-start">
          <AlertDialogTitle>Terminal Unavailable</AlertDialogTitle>
          <AlertDialogDescription>
            Terminal can only be used when the server is registered. Please register the server first.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <Button onClick={() => onOpenChange(false)}>
            OK
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
