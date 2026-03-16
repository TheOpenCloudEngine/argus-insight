"use client"

import React, { useCallback, useEffect, useRef, useState } from "react"

import useDialogState from "@/hooks/use-dialog-state"
import { fetchUsers, type PaginatedUsers } from "../api"
import { type User } from "../data/schema"

type UsersDialogType = "add" | "edit" | "delete" | "activate" | "deactivate"

type UsersContextType = {
  open: UsersDialogType | null
  setOpen: (str: UsersDialogType | null) => void
  currentRow: User | null
  setCurrentRow: React.Dispatch<React.SetStateAction<User | null>>
  statusFilter: string | null
  setStatusFilter: React.Dispatch<React.SetStateAction<string | null>>
  selectedUsers: User[]
  setSelectedUsers: React.Dispatch<React.SetStateAction<User[]>>
  users: User[]
  total: number
  page: number
  pageSize: number
  isLoading: boolean
  setPage: (page: number) => void
  setPageSize: (size: number) => void
  setSearchFilter: (search: string) => void
  setRoleFilter: (role: string) => void
  refreshUsers: () => Promise<void>
}

const UsersContext = React.createContext<UsersContextType | null>(null)

export function UsersProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useDialogState<UsersDialogType>(null)
  const [currentRow, setCurrentRow] = useState<User | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [selectedUsers, setSelectedUsers] = useState<User[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [searchFilter, setSearchFilter] = useState("")
  const [roleFilter, setRoleFilter] = useState("")
  const [isLoading, setIsLoading] = useState(true)

  // Debounce timer for search
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadUsers = useCallback(async (params: {
    page: number
    pageSize: number
    status: string | null
    role: string
    search: string
  }) => {
    try {
      setIsLoading(true)
      const data: PaginatedUsers = await fetchUsers({
        page: params.page,
        pageSize: params.pageSize,
        status: params.status || undefined,
        role: params.role || undefined,
        search: params.search || undefined,
      })
      setUsers(data.items)
      setTotal(data.total)
    } catch (err) {
      console.error("Failed to fetch users:", err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const refreshUsers = useCallback(async () => {
    await loadUsers({ page, pageSize, status: statusFilter, role: roleFilter, search: searchFilter })
  }, [loadUsers, page, pageSize, statusFilter, roleFilter, searchFilter])

  // Reload when pagination or filters change
  useEffect(() => {
    loadUsers({ page, pageSize, status: statusFilter, role: roleFilter, search: searchFilter })
  }, [loadUsers, page, pageSize, statusFilter, roleFilter, searchFilter])

  // Wrap setSearchFilter with debounce
  const handleSetSearchFilter = useCallback((search: string) => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => {
      setSearchFilter(search)
      setPage(1)
    }, 3000)
  }, [])

  // Reset to page 1 when filters change
  const handleSetStatusFilter: React.Dispatch<React.SetStateAction<string | null>> = useCallback(
    (action: React.SetStateAction<string | null>) => {
      setStatusFilter(action)
      setPage(1)
    },
    []
  )

  const handleSetRoleFilter = useCallback((role: string) => {
    setRoleFilter(role)
    setPage(1)
  }, [])

  const handleSetPageSize = useCallback((size: number) => {
    setPageSize(size)
    setPage(1)
  }, [])

  return (
    <UsersContext value={{
      open, setOpen,
      currentRow, setCurrentRow,
      statusFilter, setStatusFilter: handleSetStatusFilter,
      selectedUsers, setSelectedUsers,
      users, total, page, pageSize, isLoading,
      setPage, setPageSize: handleSetPageSize,
      setSearchFilter: handleSetSearchFilter,
      setRoleFilter: handleSetRoleFilter,
      refreshUsers,
    }}>
      {children}
    </UsersContext>
  )
}

export const useUsers = () => {
  const usersContext = React.useContext(UsersContext)

  if (!usersContext) {
    throw new Error("useUsers has to be used within <UsersProvider>")
  }

  return usersContext
}
