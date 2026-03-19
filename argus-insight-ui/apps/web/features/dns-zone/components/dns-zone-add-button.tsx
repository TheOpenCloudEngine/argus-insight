/**
 * Toolbar action buttons for the DNS Zone data table.
 *
 * Contains three button components that appear in the table toolbar:
 *
 * 1. **DnsZoneAddButton** - Dropdown menu for adding new DNS records.
 *    Lists all supported record types (except SOA) with tooltips showing
 *    what each type does. Selecting a type opens the Add Record dialog.
 *
 * 2. **DnsZoneDeleteButton** - Bulk delete button that is only enabled when
 *    one or more records are selected via checkboxes. Opens the bulk delete
 *    confirmation dialog.
 *
 * 3. **DnsZoneBindConfButton** - Opens the BIND configuration export sheet
 *    dialog for previewing and downloading BIND-compatible zone files.
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

/**
 * Dropdown button for adding a new DNS record.
 *
 * Renders a "+" button that opens a dropdown listing all DNS record types
 * (A, AAAA, CNAME, MX, TXT, NS, PTR, SRV). SOA is excluded because SOA
 * records are auto-managed by PowerDNS. Each menu item shows a tooltip
 * with a description of the record type on hover.
 *
 * Selecting a type sets the selectedRecordType in the context and opens
 * the "add" dialog.
 */
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

/**
 * Button to open the BIND configuration export sheet dialog.
 *
 * Styled with a green background to visually distinguish it as an
 * export/download action rather than a data modification.
 */
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

/**
 * Bulk delete button for removing multiple selected DNS records.
 *
 * Disabled when no records are selected (hasSelection === false).
 * When clicked, opens the "bulk-delete" confirmation dialog which
 * shows the count of selected records and asks for confirmation.
 */
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
