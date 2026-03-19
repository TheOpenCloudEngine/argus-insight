"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { MoreHorizontal, Table2, Trash2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Badge } from "@workspace/ui/components/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { UCBreadcrumbs } from "@/features/unity-catalog/components/uc-breadcrumbs"
import { UCDescriptionBox } from "@/features/unity-catalog/components/uc-description-box"
import { UCDetailsLayout } from "@/features/unity-catalog/components/uc-details-layout"
import { UCMetadataList, UCTimestampMetadata } from "@/features/unity-catalog/components/uc-metadata-list"
import { UCDeleteDialog } from "@/features/unity-catalog/components/uc-delete-dialog"
import { getTable, deleteTable } from "@/features/unity-catalog/api"
import type { UCTable } from "@/features/unity-catalog/data/schema"

export default function TableDetailsPage() {
  const params = useParams<{ catalog: string; schema: string; table: string }>()
  const router = useRouter()
  const { catalog: catalogName, schema: schemaName, table: tableName } = params
  const fullName = `${catalogName}.${schemaName}.${tableName}`
  const UC_BASE = "/dashboard/unity-catalog"

  const [table, setTable] = useState<UCTable | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await getTable(fullName)
      setTable(data)
    } finally {
      setIsLoading(false)
    }
  }, [fullName])

  useEffect(() => { loadData() }, [loadData])

  return (
    <>
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <UCBreadcrumbs items={[
            { label: "Catalogs", href: UC_BASE },
            { label: catalogName, href: `${UC_BASE}/catalogs/${catalogName}` },
            { label: schemaName, href: `${UC_BASE}/schemas/${catalogName}/${schemaName}` },
            { label: tableName },
          ]} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem className="text-destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 className="mr-2 h-4 w-4" /> Delete Table
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <UCDetailsLayout
          sidebar={
            table && (
              <div className="space-y-6">
                <UCMetadataList
                  title="Table details"
                  items={[
                    { label: "Table type", value: table.table_type },
                    { label: "Data source format", value: table.data_source_format },
                    { label: "Storage location", value: table.storage_location },
                  ]}
                />
                <UCTimestampMetadata createdAt={table.created_at} updatedAt={table.updated_at} />
              </div>
            )
          }
        >
          {table && <UCDescriptionBox comment={table.comment} />}

          {/* Columns list */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold">Columns</h4>
            {isLoading ? (
              <p className="text-muted-foreground text-sm">Loading columns...</p>
            ) : table?.columns && table.columns.length > 0 ? (
              <div className="overflow-hidden rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[10%]">#</TableHead>
                      <TableHead className="w-[50%]">Name</TableHead>
                      <TableHead className="w-[40%]">Type</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {table.columns.map((col) => (
                      <TableRow key={col.name}>
                        <TableCell className="text-muted-foreground tabular-nums">{col.position}</TableCell>
                        <TableCell className="font-medium">{col.name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{col.type_name}</Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No columns defined.</p>
            )}
          </div>
        </UCDetailsLayout>
      </div>

      <UCDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        entityType="table"
        entityName={fullName}
        onConfirm={async () => {
          await deleteTable(fullName)
          router.push(`${UC_BASE}/schemas/${catalogName}/${schemaName}`)
        }}
      />
    </>
  )
}
