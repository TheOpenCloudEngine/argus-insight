"use client"

import { UsersActionDialog } from "./users-action-dialog"
import { UsersDeleteDialog } from "./users-delete-dialog"
import { UsersStatusDialog } from "./users-status-dialog"
import { useUsers } from "./users-provider"

export function UsersDialogs() {
  const { open, setOpen, currentRow, setCurrentRow, selectedUsers } = useUsers()
  return (
    <>
      <UsersActionDialog
        key="user-add"
        open={open === "add"}
        onOpenChange={() => setOpen("add")}
      />

      <UsersStatusDialog
        key="user-activate"
        open={open === "activate"}
        onOpenChange={() => setOpen("activate")}
        selectedUsers={selectedUsers}
        type="activate"
      />

      <UsersStatusDialog
        key="user-deactivate"
        open={open === "deactivate"}
        onOpenChange={() => setOpen("deactivate")}
        selectedUsers={selectedUsers}
        type="deactivate"
      />

      {currentRow && (
        <>
          <UsersActionDialog
            key={`user-edit-${currentRow.id}`}
            open={open === "edit"}
            onOpenChange={() => {
              setOpen("edit")
              setTimeout(() => {
                setCurrentRow(null)
              }, 500)
            }}
            currentRow={currentRow}
          />

          <UsersDeleteDialog
            key={`user-delete-${currentRow.id}`}
            open={open === "delete"}
            onOpenChange={() => {
              setOpen("delete")
              setTimeout(() => {
                setCurrentRow(null)
              }, 500)
            }}
            currentRow={currentRow}
          />
        </>
      )}
    </>
  )
}
