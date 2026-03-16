"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
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
  isLoading?: boolean
}

export function UsersTable({ data, isLoading }: UsersTableProps) {
  const {
    setSelectedUsers,
    total,
    page,
    pageSize,
    setPage,
    setPageSize,
    searchUsers,
  } = useUsers()

  const [rowSelection, setRowSelection] = useState({})
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])

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
    onColumnFiltersChange: setColumnFilters,
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

  // Gather current filters and trigger search
  const handleSearch = useCallback(() => {
    const statusVal = columnFilters.find((f) => f.id === "status")?.value
    const roleVal = columnFilters.find((f) => f.id === "role")?.value
    const searchVal = columnFilters.find((f) => f.id === "username")?.value

    let status: string | null = null
    if (Array.isArray(statusVal) && statusVal.length === 1) {
      status = statusVal[0]
    }

    let role = ""
    if (Array.isArray(roleVal) && roleVal.length === 1) {
      const r = roleVal[0] as string
      role = r.charAt(0).toUpperCase() + r.slice(1)
    }

    const search = typeof searchVal === "string" ? searchVal : ""

    searchUsers({ status, role, search })
  }, [columnFilters, searchUsers])

  // Clear all filters
  const handleClear = useCallback(() => {
    table.resetColumnFilters()
    table.setGlobalFilter("")
  }, [table])

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
        onSearch={handleSearch}
        onClear={handleClear}
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
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  <p className="text-muted-foreground">Loading users...</p>
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
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
