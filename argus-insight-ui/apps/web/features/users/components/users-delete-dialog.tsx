"use client"

import { useState } from "react"
import { AlertTriangle } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@workspace/ui/components/alert"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { type User } from "../data/schema"

type UsersDeleteDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentRow: User
}

export function UsersDeleteDialog({
  open,
  onOpenChange,
  currentRow,
}: UsersDeleteDialogProps) {
  const [value, setValue] = useState("")

  const handleDelete = () => {
    if (value.trim() !== currentRow.username) return

    // TODO: API 연동 시 여기서 사용자 삭제 API를 호출하세요.
    console.log("Delete user:", currentRow)
    onOpenChange(false)
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      handleConfirm={handleDelete}
      disabled={value.trim() !== currentRow.username}
      title={
        <span className="text-destructive">
          <AlertTriangle
            className="me-1 inline-block stroke-destructive"
            size={18}
          />{" "}
          Delete User
        </span>
      }
      desc={
        <div className="space-y-4">
          <p className="mb-2">
            Are you sure you want to delete{" "}
            <span className="font-bold">{currentRow.username}</span>?
            <br />
            This action will permanently remove the user with the role of{" "}
            <span className="font-bold">
              {currentRow.role.toUpperCase()}
            </span>{" "}
            from the system. This cannot be undone.
          </p>

          <Label className="my-2">
            Username:
            <Input
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Enter username to confirm deletion."
            />
          </Label>

          <Alert variant="destructive">
            <AlertTitle>Warning!</AlertTitle>
            <AlertDescription>
              Please be careful, this operation can not be rolled back.
            </AlertDescription>
          </Alert>
        </div>
      }
      confirmText="Delete"
      destructive
    />
  )
}
