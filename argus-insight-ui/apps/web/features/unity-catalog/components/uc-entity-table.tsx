"use client"

import Link from "next/link"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { formatTimestamp } from "../lib/format"

type EntityRow = {
  name: string
  created_at?: number | null
  [key: string]: unknown
}

type UCEntityTableProps<T extends EntityRow> = {
  data: T[]
  isLoading?: boolean
  emptyMessage?: string
  nameIcon?: React.ReactNode
  getHref: (item: T) => string
  extraColumns?: {
    header: string
    cell: (item: T) => React.ReactNode
    className?: string
  }[]
}

export function UCEntityTable<T extends EntityRow>({
  data,
  isLoading,
  emptyMessage = "No items found.",
  nameIcon,
  getHref,
  extraColumns,
}: UCEntityTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[60%]">Name</TableHead>
            {extraColumns?.map((col) => (
              <TableHead key={col.header} className={col.className}>{col.header}</TableHead>
            ))}
            <TableHead className="w-[30%]">Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={2 + (extraColumns?.length ?? 0)} className="h-24 text-center">
                <p className="text-muted-foreground">Loading...</p>
              </TableCell>
            </TableRow>
          ) : data.length > 0 ? (
            data.map((item) => (
              <TableRow key={item.name} className="cursor-pointer hover:bg-muted/50">
                <TableCell>
                  <Link href={getHref(item)} className="flex items-center gap-2 hover:underline">
                    {nameIcon}
                    <span>{item.name}</span>
                  </Link>
                </TableCell>
                {extraColumns?.map((col) => (
                  <TableCell key={col.header} className={col.className}>
                    {col.cell(item)}
                  </TableCell>
                ))}
                <TableCell className="text-muted-foreground">
                  {formatTimestamp(item.created_at)}
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={2 + (extraColumns?.length ?? 0)} className="h-24 text-center">
                <p className="text-muted-foreground">{emptyMessage}</p>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
