"use client"

import { UsersTable } from "./users-table"
import { useUsers } from "./users-provider"

export function UsersTableWrapper() {
  const { users, isLoading } = useUsers()

  return <UsersTable data={users} isLoading={isLoading} />
}
