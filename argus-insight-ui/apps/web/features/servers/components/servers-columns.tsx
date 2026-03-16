"use client"

import { type ColumnDef } from "@tanstack/react-table"

import { cn } from "@workspace/ui/lib/utils"
import { Badge } from "@workspace/ui/components/badge"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { DataTableColumnHeader } from "@/components/data-table/column-header"
import { serverStatusStyles } from "../data/data"
import { type Server } from "../data/schema"

export const serversColumns: ColumnDef<Server>[] = [
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
      className: cn("max-md:sticky start-0 z-10 rounded-tl-[inherit]"),
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
    accessorKey: "hostname",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Hostname" />
    ),
    cell: ({ row }) => (
      <div className="max-w-48 truncate ps-3 font-medium">{row.getValue("hostname")}</div>
    ),
    meta: {
      className: cn(
        "drop-shadow-[0_1px_2px_rgb(0_0_0_/_0.1)] dark:drop-shadow-[0_1px_2px_rgb(255_255_255_/_0.1)]",
        "ps-0.5"
      ),
    },
    enableHiding: false,
  },
  {
    accessorKey: "ipAddress",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="IP Address" />
    ),
    cell: ({ row }) => (
      <div className="text-sm text-nowrap">{row.getValue("ipAddress")}</div>
    ),
    enableHiding: false,
  },
  {
    accessorKey: "version",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Version" />
    ),
    cell: ({ row }) => (
      <div className="text-sm">{row.getValue("version") ?? "-"}</div>
    ),
    enableSorting: false,
  },
  {
    accessorKey: "osVersion",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="OS Version" />
    ),
    cell: ({ row }) => (
      <div className="max-w-48 truncate text-sm">{row.getValue("osVersion") ?? "-"}</div>
    ),
    enableSorting: false,
  },
  {
    accessorKey: "coreCount",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Core Count" />
    ),
    cell: ({ row }) => (
      <div className="text-sm text-center">{row.getValue("coreCount") ?? "-"}</div>
    ),
    enableSorting: false,
  },
  {
    accessorKey: "totalMemory",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Total Memory" />
    ),
    cell: ({ row }) => {
      const bytes = row.getValue("totalMemory") as number | null
      if (bytes == null) return <div className="text-sm text-center">-</div>
      const mib = (bytes / (1024 * 1024)).toFixed(0)
      return (
        <div className="text-sm text-right text-nowrap">{Number(mib).toLocaleString()} MiB</div>
      )
    },
    enableSorting: false,
  },
  {
    accessorKey: "cpuUsage",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="CPU Usage" />
    ),
    cell: ({ row }) => {
      const value = row.getValue("cpuUsage") as number | null
      if (value == null) return <div className="text-sm text-center">-</div>
      const color = value > 90 ? "bg-red-500" : "bg-green-500"
      return (
        <div className="flex items-center gap-2 min-w-24 px-2">
          <div className="h-2 w-full rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full", color)}
              style={{ width: `${Math.min(value, 100)}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground w-10 text-right">{value.toFixed(1)}%</span>
        </div>
      )
    },
    enableSorting: false,
  },
  {
    accessorKey: "memoryUsage",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Memory Usage" />
    ),
    cell: ({ row }) => {
      const value = row.getValue("memoryUsage") as number | null
      if (value == null) return <div className="text-sm text-center">-</div>
      const color = value > 90 ? "bg-red-500" : "bg-green-500"
      return (
        <div className="flex items-center gap-2 min-w-24 px-2">
          <div className="h-2 w-full rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full", color)}
              style={{ width: `${Math.min(value, 100)}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground w-10 text-right">{value.toFixed(1)}%</span>
        </div>
      )
    },
    enableSorting: false,
  },
  {
    accessorKey: "status",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Status" />
    ),
    cell: ({ row }) => {
      const { status } = row.original
      const badgeColor = serverStatusStyles.get(status)
      return (
        <div className="flex space-x-2">
          <Badge variant="outline" className={cn("capitalize", badgeColor)}>
            {status}
          </Badge>
        </div>
      )
    },
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
    enableHiding: false,
    enableSorting: false,
  },
]
