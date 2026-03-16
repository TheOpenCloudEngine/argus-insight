/**
 * Users Primary Action Buttons component.
 *
 * Renders the top-level action buttons for the user management page:
 * - **Activate**: Opens the bulk activate confirmation dialog for selected users.
 * - **Deactivate**: Opens the bulk deactivate confirmation dialog for selected users.
 * - **Add**: Opens the user creation form dialog.
 *
 * These buttons are placed in the page header area and operate on the users
 * selected via table checkboxes (for Activate/Deactivate) or independently (for Add).
 * Dialog state is managed through the UsersProvider context.
 */

"use client"

import { Button } from "@workspace/ui/components/button"
import { useUsers } from "./users-provider"

export function UsersPrimaryButtons() {
  const { setOpen } = useUsers()

  return (
    <div className="flex gap-2">
      <Button onClick={() => setOpen("activate")}>
        Activate
      </Button>
      <Button onClick={() => setOpen("deactivate")}>
        Deactivate
      </Button>
      <Button onClick={() => setOpen("add")}>
        Add
      </Button>
    </div>
  )
}
