/**
 * TanStack Table column definitions for the DNS Zone table.
 *
 * Columns: Select, Name, Type, Status, TTL, Data, Comment, Action.
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

export const dnsZoneColumns: ColumnDef<DnsRecord>[] = [
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
  {
    accessorKey: "name",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Name" />
    ),
    cell: ({ row }) => {
      const name = row.getValue("name") as string
      return <span className="break-all">{name}</span>
    },
    meta: {
      className: "w-full",
    },
    enableHiding: false,
  },
  {
    accessorKey: "type",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Type" className="justify-center" />
    ),
    meta: {
      className: "w-[80px]",
    },
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
  {
    id: "status",
    accessorFn: (row) => (row.disabled ? "disabled" : "enabled"),
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Status" className="justify-center" />
    ),
    meta: {
      className: "w-[90px]",
    },
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
  {
    accessorKey: "ttl",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="TTL" className="justify-center" />
    ),
    meta: {
      className: "w-[70px]",
    },
    cell: ({ row }) => (
      <div className="text-center tabular-nums">{row.getValue("ttl")}</div>
    ),
  },
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
  {
    id: "actions",
    cell: DataTableRowActions,
  },
]
