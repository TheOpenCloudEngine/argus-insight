"use client"

import React, { useCallback, useEffect, useRef, useState } from "react"

import useDialogState from "@/hooks/use-dialog-state"
import { fetchUsers, type PaginatedUsers } from "../api"
import { type User } from "../data/schema"

type UsersDialogType = "add" | "edit" | "delete" | "activate" | "deactivate"

type SearchParams = {
  status: string | null
  role: string
  search: string
}

type UsersContextType = {
  open: UsersDialogType | null
  setOpen: (str: UsersDialogType | null) => void
  currentRow: User | null
  setCurrentRow: React.Dispatch<React.SetStateAction<User | null>>
  selectedUsers: User[]
  setSelectedUsers: React.Dispatch<React.SetStateAction<User[]>>
  users: User[]
  total: number
  page: number
  pageSize: number
  isLoading: boolean
  setPage: (page: number) => void
  setPageSize: (size: number) => void
  searchUsers: (params: SearchParams) => void
  refreshUsers: () => Promise<void>
}

const UsersContext = React.createContext<UsersContextType | null>(null)

export function UsersProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useDialogState<UsersDialogType>(null)
  const [currentRow, setCurrentRow] = useState<User | null>(null)
  const [selectedUsers, setSelectedUsers] = useState<User[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [isLoading, setIsLoading] = useState(true)

  // Applied filters (last searched values)
  const appliedFiltersRef = useRef<SearchParams>({ status: null, role: "", search: "" })

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

  // Initial load
  useEffect(() => {
    loadUsers({ page: 1, pageSize, status: null, role: "", search: "" })
  }, [loadUsers, pageSize])

  // Reload when pagination changes (using last applied filters)
  const handleSetPage = useCallback((newPage: number) => {
    setPage(newPage)
    const f = appliedFiltersRef.current
    loadUsers({ page: newPage, pageSize, status: f.status, role: f.role, search: f.search })
  }, [loadUsers, pageSize])

  const handleSetPageSize = useCallback((size: number) => {
    setPageSize(size)
    setPage(1)
    const f = appliedFiltersRef.current
    loadUsers({ page: 1, pageSize: size, status: f.status, role: f.role, search: f.search })
  }, [loadUsers])

  // Manual search triggered by Search button
  const searchUsers = useCallback((params: SearchParams) => {
    appliedFiltersRef.current = params
    setPage(1)
    loadUsers({ page: 1, pageSize, status: params.status, role: params.role, search: params.search })
  }, [loadUsers, pageSize])

  const refreshUsers = useCallback(async () => {
    const f = appliedFiltersRef.current
    await loadUsers({ page, pageSize, status: f.status, role: f.role, search: f.search })
  }, [loadUsers, page, pageSize])

  return (
    <UsersContext value={{
      open, setOpen,
      currentRow, setCurrentRow,
      selectedUsers, setSelectedUsers,
      users, total, page, pageSize, isLoading,
      setPage: handleSetPage, setPageSize: handleSetPageSize,
      searchUsers,
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
