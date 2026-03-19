/**
 * DNS Zone Data Table component.
 *
 * Renders the DNS records table with client-side filtering, sorting,
 * and row selection for bulk operations.
 * Search filters on name and content columns with 3-second debounce.
 */

"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  type ColumnFiltersState,
  type FilterFn,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
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
import { X } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { DataTableBulkActions, DataTableToolbar } from "@/components/data-table"
import { recordStatuses, recordTypes } from "../data/data"
import { type DnsRecord } from "../data/schema"
import { dnsZoneColumns as columns } from "./dns-zone-columns"
import { DnsZoneAddButton, DnsZoneDeleteButton } from "./dns-zone-add-button"
import { useDnsZone } from "./dns-zone-provider"

/** Custom global filter: match name or content fields only. */
const nameContentFilter: FilterFn<DnsRecord> = (row, _columnId, filterValue) => {
  const search = (filterValue as string).toLowerCase()
  const name = (row.original.name ?? "").toLowerCase()
  const content = (row.original.content ?? "").toLowerCase()
  return name.includes(search) || content.includes(search)
}

type DnsZoneTableProps = {
  data: DnsRecord[]
  isLoading?: boolean
}

export function DnsZoneTable({ data, isLoading }: DnsZoneTableProps) {
  const { setSelectedRecords } = useDnsZone()
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [globalFilter, setGlobalFilter] = useState("")
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      globalFilter,
      rowSelection,
    },
    enableRowSelection: true,
    globalFilterFn: nameContentFilter,
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
  })

  // Sync selected rows to provider context
  useEffect(() => {
    setSelectedRecords(table.getSelectedRowModel().rows.map((row) => row.original))
  }, [rowSelection])

  // Debounce: apply global filter 3 seconds after last input change
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      // globalFilter is already set via onGlobalFilterChange, TanStack applies it automatically
    }, 3000)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [globalFilter])

  const handleClear = useCallback(() => {
    table.resetColumnFilters()
    setGlobalFilter("")
  }, [table])

  return (
    <div className={cn("flex flex-1 flex-col gap-4")}>
      <DataTableToolbar
        table={table}
        searchPlaceholder="Filter records..."
        filters={[
          {
            columnId: "type",
            title: "Type",
            options: recordTypes.map((t) => ({ ...t })),
          },
          {
            columnId: "status",
            title: "Status",
            options: recordStatuses.map((s) => ({ ...s })),
          },
        ]}
        onClear={handleClear}
        extraActions={
          <>
            <DnsZoneAddButton />
            <DnsZoneDeleteButton />
          </>
        }
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
                      "bg-background group-hover/row:bg-muted group-data-[state=selected]/row:bg-muted",
                      (header.column.columnDef.meta as { className?: string })?.className,
                      (header.column.columnDef.meta as { thClassName?: string })?.thClassName,
                    )}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  <p className="text-muted-foreground">Loading DNS records...</p>
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
                        (cell.column.columnDef.meta as { className?: string })?.className,
                        (cell.column.columnDef.meta as { tdClassName?: string })?.tdClassName,
                      )}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Bulk actions bar: appears when one or more rows are selected */}
      <DataTableBulkActions table={table} entityName="record" />
    </div>
  )
}
