"use client"

import { useCallback, useMemo, useState } from "react"
import {
  type ColumnFiltersState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
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
import { DataTablePagination, DataTableToolbar } from "@/components/data-table"
import { type DatasetSummary } from "../data/schema"
import { datasetsColumns as columns } from "./datasets-columns"
import { DatasetsPrimaryButtons } from "./datasets-primary-buttons"
import { useDatasets } from "./datasets-provider"

type DatasetsTableProps = {
  data: DatasetSummary[]
  isLoading?: boolean
}

export function DatasetsTable({ data, isLoading }: DatasetsTableProps) {
  const { total, page, pageSize, setPage, setPageSize, searchDatasets } =
    useDatasets()

  const [sorting, setSorting] = useState<SortingState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])

  const pageCount = useMemo(
    () => Math.ceil(total / pageSize),
    [total, pageSize]
  )

  const table = useReactTable({
    data,
    columns,
    pageCount,
    state: {
      sorting,
      pagination: { pageIndex: page - 1, pageSize },
      columnFilters,
      columnVisibility,
    },
    manualPagination: true,
    manualFiltering: true,
    onPaginationChange: (updater) => {
      const next =
        typeof updater === "function"
          ? updater({ pageIndex: page - 1, pageSize })
          : updater
      if (next.pageSize !== pageSize) {
        setPageSize(next.pageSize)
      } else {
        setPage(next.pageIndex + 1)
      }
    },
    onColumnFiltersChange: setColumnFilters,
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const handleSearch = useCallback(() => {
    const searchVal = columnFilters.find((f) => f.id === "name")?.value
    const originVal = columnFilters.find((f) => f.id === "origin")?.value
    const platformVal = columnFilters.find(
      (f) => f.id === "platform_display_name"
    )?.value

    let origin = ""
    if (Array.isArray(originVal) && originVal.length === 1) {
      origin = originVal[0]
    }

    let platform = ""
    if (Array.isArray(platformVal) && platformVal.length === 1) {
      platform = platformVal[0]
    }

    const search = typeof searchVal === "string" ? searchVal : ""

    searchDatasets({ search, platform, origin, tag: "" })
  }, [columnFilters, searchDatasets])

  const handleClear = useCallback(() => {
    table.resetColumnFilters()
    table.setGlobalFilter("")
  }, [table])

  return (
    <div className={cn("flex flex-1 flex-col gap-4")}>
      <DataTableToolbar
        table={table}
        searchPlaceholder="Search datasets..."
        searchKey="name"
        filters={[
          {
            columnId: "origin",
            title: "Environment",
            options: [
              { label: "PROD", value: "PROD" },
              { label: "DEV", value: "DEV" },
              { label: "STAGING", value: "STAGING" },
            ],
          },
        ]}
        onSearch={handleSearch}
        onClear={handleClear}
        extraActions={<DatasetsPrimaryButtons />}
      />

      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="group/row">
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    className={cn(
                      "bg-background group-hover/row:bg-muted",
                      (header.column.columnDef.meta as { className?: string })
                        ?.className
                    )}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
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
                  <p className="text-muted-foreground">Loading datasets...</p>
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="group/row">
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={cn(
                        "bg-background group-hover/row:bg-muted",
                        (cell.column.columnDef.meta as { className?: string })
                          ?.className
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
                  No datasets found.
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
