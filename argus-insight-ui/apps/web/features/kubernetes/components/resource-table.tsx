"use client"

import { useCallback, useMemo, useState } from "react"
import Link from "next/link"
import { Input } from "@workspace/ui/components/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Search, RefreshCw } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import type { K8sResourceItem } from "../types"
import type { ColumnDef, ResourceDef } from "../lib/resource-definitions"
import { RESOURCE_URL_MAP } from "../lib/resource-definitions"
import { formatAge, getNestedValue } from "../lib/formatters"
import { StatusBadge } from "./status-badge"

interface ResourceTableProps {
  resourceDef: ResourceDef
  items: K8sResourceItem[]
  loading: boolean
  error?: string | null
  namespace?: string
  onRefresh?: () => void
}

export function ResourceTable({
  resourceDef,
  items,
  loading,
  error,
  namespace,
  onRefresh,
}: ResourceTableProps) {
  const [search, setSearch] = useState("")

  const filteredItems = useMemo(() => {
    if (!search) return items
    const q = search.toLowerCase()
    return items.filter((item) => {
      const name = item.metadata.name?.toLowerCase() || ""
      const ns = item.metadata.namespace?.toLowerCase() || ""
      return name.includes(q) || ns.includes(q)
    })
  }, [items, search])

  const getCellValue = useCallback(
    (item: K8sResourceItem, col: ColumnDef) => {
      if (typeof col.accessor === "function") {
        return col.accessor(item)
      }
      return getNestedValue(item as unknown as Record<string, unknown>, col.accessor)
    },
    [],
  )

  const renderCell = useCallback(
    (item: K8sResourceItem, col: ColumnDef) => {
      const value = getCellValue(item, col)
      const strValue = value === null || value === undefined ? "" : String(value)

      switch (col.render) {
        case "age":
          return (
            <span className="text-muted-foreground text-xs">
              {formatAge(strValue)}
            </span>
          )
        case "status-badge":
          return <StatusBadge status={strValue} />
        case "link": {
          const baseUrl = RESOURCE_URL_MAP[resourceDef.plural]
          const ns = item.metadata.namespace
          const name = item.metadata.name
          const href = ns
            ? `${baseUrl}/${encodeURIComponent(name)}?namespace=${encodeURIComponent(ns)}`
            : `${baseUrl}/${encodeURIComponent(name)}`
          return (
            <Link
              href={href}
              className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
              prefetch={false}
            >
              {strValue}
            </Link>
          )
        }
        case "labels": {
          const labels = value as Record<string, string> | undefined
          if (!labels) return null
          return (
            <div className="flex flex-wrap gap-1">
              {Object.entries(labels).slice(0, 3).map(([k, v]) => (
                <span
                  key={k}
                  className="inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-xs"
                >
                  {k}={v}
                </span>
              ))}
            </div>
          )
        }
        default:
          return (
            <span className="text-sm truncate max-w-[300px] inline-block">
              {strValue}
            </span>
          )
      }
    },
    [getCellValue, resourceDef.plural],
  )

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">{error}</p>
        {onRefresh && (
          <Button variant="outline" size="sm" onClick={onRefresh} className="mt-2">
            Retry
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder={`Search ${resourceDef.pluralLabel.toLowerCase()}...`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {filteredItems.length} item{filteredItems.length !== 1 ? "s" : ""}
          </span>
          {onRefresh && (
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onRefresh}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {resourceDef.columns.map((col) => (
                <TableHead
                  key={col.header}
                  className="text-xs h-9"
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && !items.length ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {resourceDef.columns.map((col) => (
                    <TableCell key={col.header}>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : filteredItems.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={resourceDef.columns.length}
                  className="h-24 text-center text-sm text-muted-foreground"
                >
                  No {resourceDef.pluralLabel.toLowerCase()} found
                  {namespace && namespace !== "_all" ? ` in namespace "${namespace}"` : ""}
                </TableCell>
              </TableRow>
            ) : (
              filteredItems.map((item) => (
                <TableRow key={item.metadata.uid || item.metadata.name}>
                  {resourceDef.columns.map((col) => (
                    <TableCell key={col.header} className="py-1.5">
                      {renderCell(item, col)}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
