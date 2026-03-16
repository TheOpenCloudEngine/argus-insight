"use client"

import { Badge } from "@workspace/ui/components/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { cn } from "@workspace/ui/lib/utils"
import { callTypes } from "../data/data"
import { type User } from "../data/schema"

type UsersViewDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentRow: User
}

export function UsersViewDialog({
  open,
  onOpenChange,
  currentRow,
}: UsersViewDialogProps) {
  const badgeColor = callTypes.get(currentRow.status)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="text-start">
          <DialogTitle>User Details</DialogTitle>
          <DialogDescription>
            Viewing details for {currentRow.username}.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 py-4">
          <ViewField label="Username" value={currentRow.username} />
          <ViewField label="Name" value={`${currentRow.firstName} ${currentRow.lastName}`} />
          <ViewField label="Email" value={currentRow.email} />
          <ViewField label="Phone Number" value={currentRow.phoneNumber} />
          <div className="grid grid-cols-[120px_1fr] items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground">Status</span>
            <Badge variant="outline" className={cn("w-fit capitalize", badgeColor)}>
              {currentRow.status}
            </Badge>
          </div>
          <div className="grid grid-cols-[120px_1fr] items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground">Role</span>
            <span className="text-sm capitalize">{currentRow.role}</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ViewField({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[120px_1fr] items-center gap-2">
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  )
}
