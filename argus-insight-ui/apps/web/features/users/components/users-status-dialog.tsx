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
import { type User } from "../data/schema"

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

  const handleConfirm = () => {
    // TODO: API 연동 시 여기서 사용자 상태 변경 API를 호출하세요.
    // 예: await updateUsersStatus(selectedUsers.map(u => u.id), isActivate ? "active" : "inactive")
    console.log(`${isActivate ? "Activate" : "Deactivate"} users:`, selectedUsers)
    onOpenChange(false)
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader className="text-start">
          <AlertDialogTitle>
            {isActivate ? "Active User" : "Inactive User"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {isActivate
              ? "선택한 사용자를 활성 사용자로 전환하시겠습니까?"
              : "선택한 사용자를 비활성 사용자로 전환하시겠습니까?"}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-row justify-end gap-2 sm:flex-row">
          <Button className="flex-1 sm:flex-none" onClick={handleConfirm}>
            예
          </Button>
          <Button
            variant="outline"
            className="flex-1 sm:flex-none"
            onClick={() => onOpenChange(false)}
          >
            아니오
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
