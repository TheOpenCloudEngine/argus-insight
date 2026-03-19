/**
 * TanStack Table column definitions for the DNS Zone data table.
 *
 * Defines 8 columns:
 * 1. **Select** - Checkbox column for row selection (bulk operations)
 * 2. **Name** - Fully qualified domain name (sortable, always visible)
 * 3. **Type** - DNS record type badge with faceted filter (A, AAAA, CNAME, etc.)
 * 4. **Status** - Enabled/disabled badge derived from the `disabled` boolean field
 * 5. **TTL** - Time-to-live in seconds (sortable, center-aligned)
 * 6. **Data** - Record content/value (not sortable, long text truncated)
 * 7. **Comment** - Optional RRset comment (not sortable, shows dash if empty)
 * 8. **Actions** - Row action dropdown menu (edit, delete, enable/disable)
 *
 * Column metadata (via `meta`) controls CSS class names for width constraints
 * and alignment. The `filterFn` on Type and Status columns enables the
 * faceted filter in the toolbar.
 */

"use client"

import { type ColumnDef } from "@tanstack/react-table"

import { cn } from "@workspace/ui/lib/utils"
import { Badge } from "@workspace/ui/components/badge"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { DataTableColumnHeader } from "@/components/data-table/column-header"
import { LongText } from "@/components/long-text"
import { statusStyles } from "../data/data"
import { type DnsRecord } from "../data/schema"
import { DataTableRowActions } from "./data-table-row-actions"

/** Column definitions array for the DNS zone TanStack Table instance. */
export const dnsZoneColumns: ColumnDef<DnsRecord>[] = [
  // --- Checkbox column for row selection (used for bulk delete) ---
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={
          table.getIsAllPageRowsSelected() ||
          (table.getIsSomePageRowsSelected() && "indeterminate")
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
        className="translate-y-[2px]"
      />
    ),
    meta: {
      className: cn("w-12 max-w-12"),
    },
    cell: ({ row }) => (
      <div onClick={(e) => e.stopPropagation()}>
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
          className="translate-y-[2px]"
        />
      </div>
    ),
    enableSorting: false,
    enableHiding: false,
  },
  // --- Name column: FQDN of the DNS record (always visible, sortable) ---
  {
    accessorKey: "name",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Name" />
    ),
    cell: ({ row }) => {
      const name = row.getValue("name") as string
      return <LongText className="max-w-48">{name}</LongText>
    },
    enableHiding: false,
  },
  // --- Type column: DNS record type badge with faceted filtering ---
  {
    accessorKey: "type",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Type" className="justify-center" />
    ),
    cell: ({ row }) => (
      <div className="flex justify-center">
        <Badge variant="outline">{row.getValue("type")}</Badge>
      </div>
    ),
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
    enableHiding: false,
  },
  // --- Status column: derived from the `disabled` boolean, shown as colored badge ---
  // Uses accessorFn to transform the boolean into a string for faceted filtering.
  {
    id: "status",
    accessorFn: (row) => (row.disabled ? "disabled" : "enabled"),
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Status" className="justify-center" />
    ),
    cell: ({ row }) => {
      const status = row.getValue("status") as string
      const badgeColor = statusStyles.get(status)
      return (
        <div className="flex justify-center">
          <Badge variant="outline" className={cn("capitalize", badgeColor)}>
            {status}
          </Badge>
        </div>
      )
    },
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
    enableSorting: false,
  },
  // --- TTL column: time-to-live in seconds (sortable, center-aligned, tabular nums) ---
  {
    accessorKey: "ttl",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="TTL" className="justify-center" />
    ),
    cell: ({ row }) => (
      <div className="text-center tabular-nums">{row.getValue("ttl")}</div>
    ),
  },
  // --- Data column: the record's content value (e.g. IP address, hostname) ---
  {
    accessorKey: "content",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Data" />
    ),
    cell: ({ row }) => (
      <LongText className="max-w-64">{row.getValue("content")}</LongText>
    ),
    enableSorting: false,
  },
  // --- Comment column: optional RRset comment, shows em-dash if empty ---
  {
    accessorKey: "comment",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Comment" />
    ),
    cell: ({ row }) => {
      const comment = row.getValue("comment") as string
      if (!comment) return <span className="text-muted-foreground">—</span>
      return <LongText className="max-w-36">{comment}</LongText>
    },
    enableSorting: false,
  },
  // --- Actions column: row-level dropdown menu (edit, delete, toggle status) ---
  {
    id: "actions",
    cell: DataTableRowActions,
  },
]
