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

import { CheckCircle, ChevronDown, UserMinus } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"
import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import {
  DataTablePagination,
  DataTableToolbar,
} from "@/components/data-table"
import { serverStatusStyles } from "../data/data"
import { type Server } from "../data/schema"
import { serversColumns as columns } from "./servers-columns"
import { useServers } from "./servers-provider"

type ServersTableProps = {
  data: Server[]
  isLoading?: boolean
}

export function ServersTable({ data, isLoading }: ServersTableProps) {
  const {
    setSelectedServers,
    setCurrentRow,
    setOpen,
    total,
    page,
    pageSize,
    setPage,
    setPageSize,
    searchServers,
  } = useServers()

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
    setSelectedServers(table.getSelectedRowModel().rows.map((row) => row.original))
  }, [rowSelection])

  // Gather current filters and trigger search
  const handleSearch = useCallback(() => {
    const statusVal = columnFilters.find((f) => f.id === "status")?.value
    const searchVal = columnFilters.find((f) => f.id === "hostname")?.value

    const status: string[] = Array.isArray(statusVal) ? statusVal : []
    const search = typeof searchVal === "string" ? searchVal : ""

    searchServers({ status, search })
  }, [columnFilters, searchServers])

  // Clear all filters
  const handleClear = useCallback(() => {
    table.resetColumnFilters()
    table.setGlobalFilter("")
  }, [table])

  return (
    <div className={cn("flex flex-1 flex-col gap-4")}>
      <DataTableToolbar
        table={table}
        searchPlaceholder="Filter servers..."
        searchKey="hostname"
        filters={[
          {
            columnId: "status",
            title: "Status",
            options: [
              { label: "REGISTERED", value: "REGISTERED", badgeClassName: serverStatusStyles.get("REGISTERED") },
              { label: "UNREGISTERED", value: "UNREGISTERED", badgeClassName: serverStatusStyles.get("UNREGISTERED") },
              { label: "DISCONNECTED", value: "DISCONNECTED", badgeClassName: serverStatusStyles.get("DISCONNECTED") },
            ],
          },
        ]}
        onSearch={handleSearch}
        onClear={handleClear}
        extraActions={
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" className="h-8 bg-blue-600 text-white hover:bg-blue-700">
                Action
                <ChevronDown className="ml-1 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[200px]">
              <DropdownMenuItem
                onClick={() => {
                  setCurrentRow(null)
                  setOpen("approve")
                }}
              >
                Approve
                <span className="ml-auto">
                  <CheckCircle size={16} />
                </span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  setCurrentRow(null)
                  setOpen("unregister")
                }}
              >
                Remove From Manager
                <span className="ml-auto">
                  <UserMinus size={16} />
                </span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
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
                  <p className="text-muted-foreground">Loading servers...</p>
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
    </div>
  )
}
