"use client"

import { useRef, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { Button } from "@workspace/ui/components/button"
import { TerminalView, type TerminalViewHandle } from "@/features/terminal/components/terminal-view"
import { buildTerminalWsUrl } from "@/features/terminal/components/terminal-panel"
import { type Server } from "../data/schema"

type ServersTerminalDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentRow: Server
}

export function ServersTerminalDialog({
  open,
  onOpenChange,
  currentRow,
}: ServersTerminalDialogProps) {
  const terminalRef = useRef<TerminalViewHandle>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const handleDisconnect = () => {
    terminalRef.current?.disconnect()
    setConfirmOpen(false)
    onOpenChange(false)
  }

  return (
    <>
      <Dialog open={open} onOpenChange={() => {}}>
        <DialogContent
          className="max-w-5xl h-[80vh] flex flex-col"
          showCloseButton={false}
          onInteractOutside={(e) => e.preventDefault()}
          onEscapeKeyDown={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle className="font-mono text-sm">
              Terminal — {currentRow.hostname} ({currentRow.ipAddress})
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0">
            {open && (
              <TerminalView
                ref={terminalRef}
                wsUrl={buildTerminalWsUrl(currentRow.hostname)}
              />
            )}
          </div>
          <div className="flex justify-center pt-3">
            <Button
              variant="destructive"
              onClick={() => setConfirmOpen(true)}
            >
              Disconnect
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect Terminal</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to disconnect from the server?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>No</AlertDialogCancel>
            <AlertDialogAction onClick={handleDisconnect}>
              Yes
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
