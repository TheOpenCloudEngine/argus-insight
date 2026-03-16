"use client"

import { UsersTable } from "./users-table"
import { useUsers } from "./users-provider"

export function UsersTableWrapper() {
  const { users, isLoading } = useUsers()

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-muted-foreground">Loading users...</p>
      </div>
    )
  }

  return <UsersTable data={users} />
}
