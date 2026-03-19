"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Brain, MoreHorizontal, Trash2 } from "lucide-react"
import Link from "next/link"

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
import { UCTimestampMetadata } from "@/features/unity-catalog/components/uc-metadata-list"
import { UCDeleteDialog } from "@/features/unity-catalog/components/uc-delete-dialog"
import { getModel, updateModel, deleteModel, listModelVersions } from "@/features/unity-catalog/api"
import { formatTimestamp } from "@/features/unity-catalog/lib/format"
import type { Model, ModelVersion } from "@/features/unity-catalog/data/schema"

const statusColors: Record<string, string> = {
  READY: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  PENDING_REGISTRATION: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  FAILED_REGISTRATION: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
}

export default function ModelDetailsPage() {
  const params = useParams<{ catalog: string; schema: string; model: string }>()
  const router = useRouter()
  const { catalog: catalogName, schema: schemaName, model: modelName } = params
  const fullName = `${catalogName}.${schemaName}.${modelName}`
  const UC_BASE = "/dashboard/unity-catalog"

  const [model, setModel] = useState<Model | null>(null)
  const [versions, setVersions] = useState<ModelVersion[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [m, v] = await Promise.all([getModel(fullName), listModelVersions(fullName)])
      setModel(m)
      setVersions(v)
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
            { label: modelName },
          ]} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem className="text-destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 className="mr-2 h-4 w-4" /> Delete Model
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <UCDetailsLayout
          sidebar={
            model && <UCTimestampMetadata createdAt={model.created_at} updatedAt={model.updated_at} />
          }
        >
          {model && (
            <UCDescriptionBox
              comment={model.comment}
              onEdit={async (comment) => {
                await updateModel(fullName, { comment })
                loadData()
              }}
            />
          )}

          {/* Versions table */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold">Versions</h4>
            {isLoading ? (
              <p className="text-muted-foreground text-sm">Loading versions...</p>
            ) : versions.length > 0 ? (
              <div className="overflow-hidden rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[15%]">Status</TableHead>
                      <TableHead className="w-[20%]">Version</TableHead>
                      <TableHead className="w-[35%]">Comment</TableHead>
                      <TableHead className="w-[30%]">Created At</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {versions.map((v) => (
                      <TableRow key={v.version} className="cursor-pointer hover:bg-muted/50">
                        <TableCell>
                          <Badge variant="outline" className={statusColors[v.status ?? ""] ?? ""}>
                            {v.status ?? "—"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Link
                            href={`${UC_BASE}/models/${catalogName}/${schemaName}/${modelName}/versions/${v.version}`}
                            className="font-medium hover:underline"
                          >
                            v{v.version}
                          </Link>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {v.comment ?? "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatTimestamp(v.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No versions registered.</p>
            )}
          </div>
        </UCDetailsLayout>
      </div>

      <UCDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        entityType="model"
        entityName={fullName}
        onConfirm={async () => {
          await deleteModel(fullName)
          router.push(`${UC_BASE}/schemas/${catalogName}/${schemaName}`)
        }}
      />
    </>
  )
}
