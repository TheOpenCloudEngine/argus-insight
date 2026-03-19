/**
 * Add Record dropdown button.
 *
 * Displays a dropdown menu with DNS record types (A, AAAA, CNAME, etc.).
 * Selecting a type opens the add record dialog with the appropriate form.
 */

"use client"

import { Plus } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { recordTypes } from "../data/data"
import { useDnsZone } from "./dns-zone-provider"

export function DnsZoneAddButton() {
  const { setOpen, setSelectedRecordType } = useDnsZone()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" className="h-8">
          <Plus className="mr-1.5 h-4 w-4" />
          Add Record
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[140px]">
        {recordTypes.map((type) => (
          <DropdownMenuItem
            key={type.value}
            onClick={() => {
              setSelectedRecordType(type.value)
              setOpen("add")
            }}
          >
            {type.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
