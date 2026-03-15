"use client"

import React, { useState } from "react"

import useDialogState from "@/hooks/use-dialog-state"
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
}

const UsersContext = React.createContext<UsersContextType | null>(null)

export function UsersProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useDialogState<UsersDialogType>(null)
  const [currentRow, setCurrentRow] = useState<User | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [selectedUsers, setSelectedUsers] = useState<User[]>([])

  return (
    <UsersContext value={{ open, setOpen, currentRow, setCurrentRow, statusFilter, setStatusFilter, selectedUsers, setSelectedUsers }}>
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
