/**
 * User Delete Confirmation Dialog component.
 *
 * A destructive confirmation dialog that requires the admin to type the target
 * user's username before the delete operation is allowed. This two-step
 * confirmation prevents accidental deletion of user accounts.
 *
 * Flow:
 * 1. Dialog opens showing the target user's username and role.
 * 2. Admin must type the exact username into the confirmation input.
 * 3. The "Delete" button is disabled until the typed value matches.
 * 4. On confirmation, calls `deleteUser()` API and refreshes the user list.
 *
 * The dialog also displays a prominent warning alert to emphasize that
 * the deletion is permanent and cannot be undone.
 */

"use client"

import { useState } from "react"
import { AlertTriangle } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@workspace/ui/components/alert"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { deleteUser } from "../api"
import { type User } from "../data/schema"
import { useUsers } from "./users-provider"

type UsersDeleteDialogProps = {
  /** Whether the dialog is open. */
  open: boolean
  /** Callback to open or close the dialog. */
  onOpenChange: (open: boolean) => void
  /** The user to be deleted. */
  currentRow: User
}

export function UsersDeleteDialog({
  open,
  onOpenChange,
  currentRow,
}: UsersDeleteDialogProps) {
  /** Tracks the admin's typed confirmation text (must match the username). */
  const [value, setValue] = useState("")
  const { refreshUsers } = useUsers()

  /**
   * Handle the delete confirmation.
   *
   * Only proceeds if the typed value exactly matches the target user's username.
   * Calls the deleteUser API, refreshes the list, and closes the dialog.
   */
  const [error, setError] = useState<string | null>(null)

  const handleDelete = async () => {
    if (value.trim() !== currentRow.username) return
    setError(null)

    try {
      await deleteUser(currentRow.id)
      await refreshUsers()
      onOpenChange(false)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete user"
      if (msg.includes("admin") || msg.includes("Admin")) {
        setError(msg)
      } else {
        setError(msg)
      }
    }
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
              {currentRow.role === "argus-admin" ? "Admin" : currentRow.role === "argus-superuser" ? "Superuser" : "User"}
            </span>{" "}
            from the system. This cannot be undone.
          </p>

          {/* Username confirmation input */}
          <Label className="my-2">
            Username:
            <Input
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Enter username to confirm deletion."
            />
          </Label>

          {/* Error message */}
          {error && (
            <Alert variant="destructive">
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Destructive warning banner */}
          {!error && (
            <Alert variant="destructive">
              <AlertTitle>Warning!</AlertTitle>
              <AlertDescription>
                Please be careful, this operation can not be rolled back.
              </AlertDescription>
            </Alert>
          )}
        </div>
      }
      confirmText="Delete"
      destructive
    />
  )
}
