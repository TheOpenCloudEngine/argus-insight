/**
 * Data Table Row Actions component (DNS Zone).
 *
 * Renders a "..." (more) dropdown menu button in each row of the DNS zone
 * data table. The dropdown provides three per-row actions:
 *
 * 1. **Edit** - Opens the edit dialog with the current record pre-populated.
 *    Sets the currentRow in the provider context and opens the "edit" dialog.
 *
 * 2. **Delete** - Opens the single-record delete confirmation dialog.
 *    Sets the currentRow and opens the "delete" dialog.
 *
 * 3. **Enable/Disable** - Toggles the record's enabled/disabled status
 *    directly without a confirmation dialog. Sends a REPLACE patch to
 *    PowerDNS with the `disabled` flag flipped, then refreshes the table.
 *
 * The dropdown uses `modal={false}` to prevent focus trapping issues when
 * the dropdown triggers another dialog (edit/delete).
 */

"use client"

import { type Row } from "@tanstack/react-table"
import { Ban, CheckCircle, MoreHorizontal, Pencil, Trash2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { type DnsRecord } from "../data/schema"
import { updateZoneRecords } from "../api"
import { useDnsZone } from "./dns-zone-provider"

/** Props for the DataTableRowActions component (received from TanStack Table cell renderer). */
type DataTableRowActionsProps = {
  /** The table row containing the DNS record data */
  row: Row<DnsRecord>
}

/**
 * Row-level action dropdown menu for the DNS zone table.
 *
 * Provides Edit, Delete, and Enable/Disable actions for each individual
 * DNS record. The toggle action sends an immediate API call without
 * confirmation since it is easily reversible.
 */
export function DataTableRowActions({ row }: DataTableRowActionsProps) {
  const { setOpen, setCurrentRow, refreshRecords } = useDnsZone()
  const record = row.original

  // Track whether the record is currently disabled to show the correct toggle label
  const isDisabled = record.disabled

  /**
   * Toggle the record's enabled/disabled status.
   *
   * Sends a REPLACE patch with the `disabled` flag flipped. Uses REPLACE
   * (not a dedicated toggle endpoint) because PowerDNS only supports
   * full RRset replacement. The rest of the record data stays the same.
   */
  async function handleToggleStatus() {
    try {
      await updateZoneRecords([
        {
          name: record.name,
          type: record.type,
          ttl: record.ttl,
          changetype: "REPLACE",
          records: [{ content: record.content, disabled: !isDisabled }],
        },
      ])
      await refreshRecords()
    } catch (err) {
      console.error("Failed to toggle record status:", err)
    }
  }

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
            setCurrentRow(record)
            setOpen("edit")
          }}
        >
          Edit
          <span className="ml-auto">
            <Pencil size={16} />
          </span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => {
            setCurrentRow(record)
            setOpen("delete")
          }}
          className="text-red-500!"
        >
          Delete
          <span className="ml-auto">
            <Trash2 size={16} />
          </span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleToggleStatus}>
          {isDisabled ? "Enable" : "Disable"}
          <span className="ml-auto">
            {isDisabled ? <CheckCircle size={16} /> : <Ban size={16} />}
          </span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
