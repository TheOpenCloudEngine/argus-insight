/**
 * Add Record dropdown button and Delete Records button.
 */

"use client"

import { FileCode2, Plus, Trash2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import { recordTypes, recordTypeDescriptions } from "../data/data"
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
        <TooltipProvider delayDuration={300}>
          {recordTypes
            .filter((t) => t.value !== "SOA")
            .map((type) => (
              <Tooltip key={type.value}>
                <TooltipTrigger asChild>
                  <DropdownMenuItem
                    onClick={() => {
                      setSelectedRecordType(type.value)
                      setOpen("add")
                    }}
                  >
                    {type.label}
                  </DropdownMenuItem>
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-[250px]">
                  <p className="text-xs">{recordTypeDescriptions[type.value]}</p>
                </TooltipContent>
              </Tooltip>
            ))}
        </TooltipProvider>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function DnsZoneBindConfButton() {
  const { setOpen } = useDnsZone()

  return (
    <Button
      size="sm"
      className="h-8 bg-green-600 text-white hover:bg-green-700"
      onClick={() => setOpen("bind-conf")}
    >
      <FileCode2 className="mr-1.5 h-4 w-4" />
      Linux BIND
    </Button>
  )
}

export function DnsZoneDeleteButton() {
  const { selectedRecords, setOpen } = useDnsZone()
  const hasSelection = selectedRecords.length > 0

  return (
    <Button
      size="sm"
      variant="destructive"
      className="h-8"
      disabled={!hasSelection}
      onClick={() => setOpen("bulk-delete")}
    >
      <Trash2 className="mr-1.5 h-4 w-4" />
      Delete Records
    </Button>
  )
}
