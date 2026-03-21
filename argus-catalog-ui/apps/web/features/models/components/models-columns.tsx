"use client"

import { type ColumnDef } from "@tanstack/react-table"
import { MoreHorizontal, User } from "lucide-react"
import Link from "next/link"

import { Checkbox } from "@workspace/ui/components/checkbox"
import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { type ModelSummary } from "../data/schema"

/** Format bytes to human-readable string. */
function formatSize(bytes: number | null | undefined): string {
  if (bytes == null || bytes === 0) return "-"
  const units = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, i)
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** Status badge — colored pill with uppercase label. */
function VersionStatusBadge({ status }: { status: string | null | undefined }) {
  let bg = "bg-orange-500"
  let label = "N/A"

  if (status === "READY") {
    bg = "bg-blue-500"
    label = "READY"
  } else if (status === "PENDING_REGISTRATION") {
    bg = "bg-zinc-400"
    label = "PENDING"
  } else if (status === "FAILED_REGISTRATION") {
    bg = "bg-red-500"
    label = "FAILED"
  }

  return (
    <span
      className={`inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-[10px] font-semibold text-white ${bg}`}
    >
      {label}
    </span>
  )
}

export const modelsColumns: ColumnDef<ModelSummary>[] = [
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
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
        onClick={(e) => e.stopPropagation()}
      />
    ),
    enableSorting: false,
    enableHiding: false,
    meta: { className: "w-[40px] text-center" },
  },
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <div className="min-w-0">
        <Link
          href={`/dashboard/models/${encodeURIComponent(row.original.name)}`}
          className="font-medium text-sm hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {row.original.name}
        </Link>
        {row.original.description && (
          <p className="text-xs text-muted-foreground truncate max-w-[400px]">
            {row.original.description}
          </p>
        )}
      </div>
    ),
  },
  {
    accessorKey: "owner",
    header: () => <span className="w-full text-center block">Owner</span>,
    cell: ({ row }) =>
      row.original.owner ? (
        <div className="flex items-center justify-center gap-1.5">
          <User className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-sm">{row.original.owner}</span>
        </div>
      ) : (
        <span className="text-sm text-muted-foreground text-center block">-</span>
      ),
    meta: { className: "w-[140px] text-center" },
  },
  {
    id: "versions",
    header: () => <span className="w-full text-center block">Version</span>,
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground text-center block">
        v{row.original.max_version_number}
      </span>
    ),
    meta: { className: "w-[80px] text-center" },
  },
  {
    id: "latest_version_status",
    header: () => <span className="w-full text-center block">Status</span>,
    cell: ({ row }) => (
      <div className="flex justify-center">
        <VersionStatusBadge status={row.original.latest_version_status} />
      </div>
    ),
    meta: { className: "w-[90px] text-center" },
  },
  {
    id: "sklearn_version",
    header: () => <span className="w-full text-center block">sklearn</span>,
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground text-center block">
        {row.original.sklearn_version ?? "-"}
      </span>
    ),
    meta: { className: "w-[90px] text-center" },
  },
  {
    id: "python_version",
    header: () => <span className="w-full text-center block">Python</span>,
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground text-center block">
        {row.original.python_version ?? "-"}
      </span>
    ),
    meta: { className: "w-[90px] text-center" },
  },
  {
    id: "model_size_bytes",
    header: () => <span className="w-full text-center block">Size</span>,
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground text-center block">
        {formatSize(row.original.model_size_bytes)}
      </span>
    ),
    meta: { className: "w-[90px] text-center" },
  },
  {
    id: "updated_at",
    header: () => <span className="w-full text-center block">Updated</span>,
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground text-center block">
        {new Date(row.original.updated_at).toLocaleDateString("en-US", {
          year: "numeric",
          month: "short",
          day: "numeric",
        })}
      </span>
    ),
    meta: { className: "w-[120px] text-center" },
  },
  {
    id: "actions",
    cell: ({ row }) => (
      <div className="flex justify-center">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="h-8 w-8 p-0"
              onClick={(e) => e.stopPropagation()}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link href={`/dashboard/models/${encodeURIComponent(row.original.name)}`}>
                View Details
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    ),
    meta: { className: "w-[50px] text-center" },
  },
]
