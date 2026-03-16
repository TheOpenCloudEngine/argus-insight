"use client"

import { type Row } from "@tanstack/react-table"
import { MoreHorizontal, Search, Terminal } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { type Server } from "../data/schema"

type DataTableRowActionsProps = {
  row: Row<Server>
}

export function DataTableRowActions({ row }: DataTableRowActionsProps) {
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="flex h-8 w-8 p-0 data-[state=open]:bg-muted"
        >
          <MoreHorizontal className="h-4 w-4" />
          <span className="sr-only">Open menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[160px]">
        <DropdownMenuItem
          onClick={() => {
            console.log("Inspect server:", row.original.hostname)
          }}
        >
          Inspect
          <span className="ml-auto">
            <Search size={16} />
          </span>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => {
            console.log("Terminal server:", row.original.hostname)
          }}
        >
          Terminal
          <span className="ml-auto">
            <Terminal size={16} />
          </span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
