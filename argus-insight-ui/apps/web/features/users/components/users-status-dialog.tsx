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
import { activateUser, deactivateUser } from "../api"
import { type User } from "../data/schema"
import { useUsers } from "./users-provider"

type UsersStatusDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  selectedUsers: User[]
  type: "activate" | "deactivate"
}

export function UsersStatusDialog({
  open,
  onOpenChange,
  selectedUsers,
  type,
}: UsersStatusDialogProps) {
  const isActivate = type === "activate"
  const { refreshUsers } = useUsers()

  const handleConfirm = async () => {
    try {
      const fn = isActivate ? activateUser : deactivateUser
      await Promise.all(selectedUsers.map((u) => fn(u.id)))
      await refreshUsers()
    } catch (err) {
      console.error(`Failed to ${type} users:`, err)
    }
    onOpenChange(false)
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader className="text-start">
          <AlertDialogTitle>
            {isActivate ? "Activate User" : "Deactivate User"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {isActivate
              ? `Are you sure you want to activate ${selectedUsers.length} selected user(s)?`
              : `Are you sure you want to deactivate ${selectedUsers.length} selected user(s)?`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-row justify-end gap-2 sm:flex-row">
          <Button className="flex-1 sm:flex-none" onClick={handleConfirm}>
            Confirm
          </Button>
          <Button
            variant="outline"
            className="flex-1 sm:flex-none"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
