/**
 * TanStack Table column definitions for the DNS Zone table.
 *
 * Columns: Name, Type, Status, TTL, Data, Comment, Action.
 */

"use client"

import { type ColumnDef } from "@tanstack/react-table"

import { cn } from "@workspace/ui/lib/utils"
import { Badge } from "@workspace/ui/components/badge"
import { DataTableColumnHeader } from "@/components/data-table/column-header"
import { LongText } from "@/components/long-text"
import { statusStyles } from "../data/data"
import { type DnsRecord } from "../data/schema"
import { DataTableRowActions } from "./data-table-row-actions"

export const dnsZoneColumns: ColumnDef<DnsRecord>[] = [
  /**
   * Name column — the DNS record name (e.g. "www.example.com.").
   */
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
  /**
   * Type column — the DNS record type (A, AAAA, CNAME, MX, etc.).
   * Supports faceted filtering.
   */
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
  /**
   * Status column — Enabled or Disabled.
   * Derived from the `disabled` boolean field.
   */
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
  /**
   * TTL column — Time to Live in seconds.
   */
  {
    accessorKey: "ttl",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="TTL" className="justify-center" />
    ),
    cell: ({ row }) => (
      <div className="text-center tabular-nums">{row.getValue("ttl")}</div>
    ),
  },
  /**
   * Data column — the record content (IP address, hostname, etc.).
   */
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
  /**
   * Comment column — optional comment on the RRset.
   */
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
  /**
   * Action column — row-level dropdown menu (Edit, Delete).
   */
  {
    id: "actions",
    cell: DataTableRowActions,
  },
]
