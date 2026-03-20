"use client"

import { type ColumnDef } from "@tanstack/react-table"
import { Database, MoreHorizontal, Tags, Users } from "lucide-react"
import Link from "next/link"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { type DatasetSummary } from "../data/schema"

export const datasetsColumns: ColumnDef<DatasetSummary>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <div className="min-w-0">
        <Link
          href={`/dashboard/datasets/${row.original.id}`}
          className="font-medium text-sm hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {row.original.name}
        </Link>
        <p className="text-xs text-muted-foreground truncate max-w-[400px]">
          {row.original.description || row.original.urn}
        </p>
      </div>
    ),
  },
  {
    accessorKey: "platform_display_name",
    header: "Platform",
    cell: ({ row }) => (
      <div className="flex items-center gap-1.5">
        <Database className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-sm">{row.original.platform_display_name}</span>
      </div>
    ),
    meta: { className: "w-[150px]" },
  },
  {
    accessorKey: "origin",
    header: "Environment",
    cell: ({ row }) => (
      <Badge variant="outline" className="text-xs">
        {row.original.origin}
      </Badge>
    ),
    meta: { className: "w-[120px]" },
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.original.status
      return (
        <Badge
          variant={
            status === "active"
              ? "default"
              : status === "deprecated"
                ? "secondary"
                : "destructive"
          }
          className="text-xs"
        >
          {status}
        </Badge>
      )
    },
    meta: { className: "w-[100px]" },
  },
  {
    id: "schema_field_count",
    header: "Fields",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.schema_field_count}
      </span>
    ),
    meta: { className: "w-[70px]" },
  },
  {
    id: "tag_count",
    header: () => <Tags className="h-4 w-4" />,
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.tag_count}
      </span>
    ),
    meta: { className: "w-[50px]" },
  },
  {
    id: "owner_count",
    header: () => <Users className="h-4 w-4" />,
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.owner_count}
      </span>
    ),
    meta: { className: "w-[50px]" },
  },
  {
    id: "actions",
    cell: ({ row }) => (
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
            <Link href={`/dashboard/datasets/${row.original.id}`}>
              View Details
            </Link>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
    meta: { className: "w-[50px]" },
  },
]
