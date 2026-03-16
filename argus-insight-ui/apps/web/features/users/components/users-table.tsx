"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import {
  type ColumnFiltersState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"

import { cn } from "@workspace/ui/lib/utils"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import {
  DataTableBulkActions,
  DataTablePagination,
  DataTableToolbar,
} from "@/components/data-table"
import { roles } from "../data/data"
import { type User } from "../data/schema"
import { usersColumns as columns } from "./users-columns"
import { useUsers } from "./users-provider"

type UsersTableProps = {
  data: User[]
}

export function UsersTable({ data }: UsersTableProps) {
  const {
    statusFilter,
    setStatusFilter,
    setSelectedUsers,
    total,
    page,
    pageSize,
    setPage,
    setPageSize,
    setSearchFilter,
    setRoleFilter,
  } = useUsers()

  const [rowSelection, setRowSelection] = useState({})
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])

  // Track whether columnFilter change came from external statusFilter sync
  const skipPropagation = useRef(false)

  // Sync statusFilter from context → columnFilters (for display in toolbar)
  useEffect(() => {
    skipPropagation.current = true
    setColumnFilters((prev) => {
      const without = prev.filter((f) => f.id !== "status")
      return statusFilter ? [...without, { id: "status", value: [statusFilter] }] : without
    })
  }, [statusFilter])

  const pageCount = useMemo(() => Math.ceil(total / pageSize), [total, pageSize])

  const table = useReactTable({
    data,
    columns,
    pageCount,
    state: {
      sorting,
      pagination: { pageIndex: page - 1, pageSize },
      rowSelection,
      columnFilters,
      columnVisibility,
    },
    enableRowSelection: true,
    manualPagination: true,
    manualFiltering: true,
    onPaginationChange: (updater) => {
      const next = typeof updater === "function"
        ? updater({ pageIndex: page - 1, pageSize })
        : updater
      if (next.pageSize !== pageSize) {
        setPageSize(next.pageSize)
      } else {
        setPage(next.pageIndex + 1)
      }
    },
    onColumnFiltersChange: (updater) => {
      const next = typeof updater === "function" ? updater(columnFilters) : updater
      setColumnFilters(next)

      // Skip server call if this change came from statusFilter context sync
      if (skipPropagation.current) {
        skipPropagation.current = false
        return
      }

      // Propagate filter changes to server-side query params
      const statusVal = next.find((f) => f.id === "status")?.value
      const roleVal = next.find((f) => f.id === "role")?.value
      const searchVal = next.find((f) => f.id === "username")?.value

      // Status: faceted filter returns string[], extract single value for API
      if (Array.isArray(statusVal) && statusVal.length === 1) {
        setStatusFilter(statusVal[0])
      } else {
        setStatusFilter(null)
      }

      // Role: faceted filter returns string[], capitalize for backend (admin→Admin)
      if (Array.isArray(roleVal) && roleVal.length === 1) {
        const r = roleVal[0] as string
        setRoleFilter(r.charAt(0).toUpperCase() + r.slice(1))
      } else {
        setRoleFilter("")
      }

      // Search: string from input
      if (typeof searchVal === "string") {
        setSearchFilter(searchVal)
      } else {
        setSearchFilter("")
      }
    },
    onRowSelectionChange: setRowSelection,
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
  })

  // Sync selected rows to context
  useEffect(() => {
    setSelectedUsers(table.getSelectedRowModel().rows.map((row) => row.original))
  }, [rowSelection])

  return (
    <div className={cn("flex flex-1 flex-col gap-4")}>
      <DataTableToolbar
        table={table}
        searchPlaceholder="Filter users..."
        searchKey="username"
        filters={[
          {
            columnId: "status",
            title: "Status",
            options: [
              { label: "Active", value: "active" },
              { label: "Inactive", value: "inactive" },
            ],
          },
          {
            columnId: "role",
            title: "Role",
            options: roles.map((role) => ({ ...role })),
          },
        ]}
      />
      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="group/row">
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead
                      key={header.id}
                      colSpan={header.colSpan}
                      className={cn(
                        "bg-background group-hover/row:bg-muted group-data-[state=selected]/row:bg-muted",
                        (header.column.columnDef.meta as { className?: string })
                          ?.className,
                        (
                          header.column.columnDef.meta as {
                            thClassName?: string
                          }
                        )?.thClassName
                      )}
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  className="group/row cursor-pointer"
                  onClick={() => row.toggleSelected()}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={cn(
                        "bg-background group-hover/row:bg-muted group-data-[state=selected]/row:bg-muted",
                        (cell.column.columnDef.meta as { className?: string })
                          ?.className,
                        (
                          cell.column.columnDef.meta as {
                            tdClassName?: string
                          }
                        )?.tdClassName
                      )}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <DataTablePagination table={table} className="mt-auto" />
      <DataTableBulkActions table={table} entityName="user" />
    </div>
  )
}
