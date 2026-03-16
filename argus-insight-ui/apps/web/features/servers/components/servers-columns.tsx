"use client"

import { type ColumnDef } from "@tanstack/react-table"

import { cn } from "@workspace/ui/lib/utils"
import { Badge } from "@workspace/ui/components/badge"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { DataTableColumnHeader } from "@/components/data-table/column-header"
import { serverStatusStyles } from "../data/data"
import { type Server } from "../data/schema"
import { DataTableRowActions } from "./data-table-row-actions"

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
      className: cn("w-12 max-w-12 max-md:sticky start-0 z-10 rounded-tl-[inherit]"),
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
      <DataTableColumnHeader column={column} title="Hostname" className="justify-center" />
    ),
    cell: ({ row }) => (
      <div className="text-center text-sm font-medium">{row.getValue("hostname")}</div>
    ),
    enableHiding: false,
  },
  {
    accessorKey: "ipAddress",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="IP" className="justify-center" />
    ),
    cell: ({ row }) => (
      <div className="text-center text-sm text-nowrap">{row.getValue("ipAddress")}</div>
    ),
    enableHiding: false,
  },
  {
    accessorKey: "version",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Version" className="justify-center" />
    ),
    cell: ({ row }) => (
      <div className="text-center text-sm">{row.getValue("version") ?? "-"}</div>
    ),
    enableSorting: false,
  },
  {
    accessorKey: "osVersion",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="OS" className="justify-center" />
    ),
    cell: ({ row }) => (
      <div className="text-center text-sm">{row.getValue("osVersion") ?? "-"}</div>
    ),
    enableSorting: false,
  },
  {
    accessorKey: "coreCount",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Core" className="justify-center" />
    ),
    cell: ({ row }) => (
      <div className="text-center text-sm">{row.getValue("coreCount") ?? "-"}</div>
    ),
    enableSorting: false,
  },
  {
    accessorKey: "totalMemory",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Total Memory" className="justify-center" />
    ),
    cell: ({ row }) => {
      const bytes = row.getValue("totalMemory") as number | null
      if (bytes == null) return <div className="text-center text-sm">-</div>
      const mib = (bytes / (1024 * 1024)).toFixed(0)
      return (
        <div className="text-center text-sm text-nowrap">{Number(mib).toLocaleString()} MiB</div>
      )
    },
    enableSorting: false,
  },
  {
    accessorKey: "cpuUsage",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="CPU Usage" className="justify-center" />
    ),
    cell: ({ row }) => {
      const value = row.getValue("cpuUsage") as number | null
      if (value == null) return <div className="text-center text-sm">-</div>
      const color = value > 90 ? "bg-red-500" : "bg-green-500"
      return (
        <div className="flex items-center justify-center gap-2 min-w-24 px-2">
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
      <DataTableColumnHeader column={column} title="Memory Usage" className="justify-center" />
    ),
    cell: ({ row }) => {
      const value = row.getValue("memoryUsage") as number | null
      if (value == null) return <div className="text-center text-sm">-</div>
      const color = value > 90 ? "bg-red-500" : "bg-green-500"
      return (
        <div className="flex items-center justify-center gap-2 min-w-24 px-2">
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
      <DataTableColumnHeader column={column} title="Status" className="justify-center" />
    ),
    cell: ({ row }) => {
      const { status } = row.original
      const badgeColor = serverStatusStyles.get(status)
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
    enableHiding: false,
    enableSorting: false,
  },
  {
    accessorKey: "lastHeartbeatSeconds",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Last Heartbeat" className="justify-center" />
    ),
    cell: ({ row }) => {
      const seconds = row.getValue("lastHeartbeatSeconds") as number | null
      if (seconds == null) return <div className="text-center text-sm">-</div>
      return (
        <div className="text-center text-sm text-nowrap">{seconds.toLocaleString()}s ago</div>
      )
    },
    enableSorting: false,
  },
  {
    id: "actions",
    cell: DataTableRowActions,
  },
]
