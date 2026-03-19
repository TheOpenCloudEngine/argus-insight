"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { FunctionSquare, MoreHorizontal, Trash2 } from "lucide-react"

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
import { getFunction, deleteFunction } from "@/features/unity-catalog/api"
import type { UCFunction } from "@/features/unity-catalog/data/schema"

export default function FunctionDetailsPage() {
  const params = useParams<{ catalog: string; schema: string; fn: string }>()
  const router = useRouter()
  const { catalog: catalogName, schema: schemaName, fn: fnName } = params
  const fullName = `${catalogName}.${schemaName}.${fnName}`
  const UC_BASE = "/dashboard/unity-catalog"

  const [fn, setFn] = useState<UCFunction | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      setFn(await getFunction(fullName))
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
            { label: fnName },
          ]} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem className="text-destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 className="mr-2 h-4 w-4" /> Delete Function
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <UCDetailsLayout
          sidebar={
            fn && (
              <div className="space-y-6">
                <UCMetadataList
                  title="Function details"
                  items={[
                    { label: "Language", value: fn.external_language },
                    { label: "Return type", value: fn.data_type },
                  ]}
                />
                <UCTimestampMetadata createdAt={fn.created_at} updatedAt={fn.updated_at} />
              </div>
            )
          }
        >
          {fn && <UCDescriptionBox comment={fn.comment} />}

          {/* Input parameters */}
          {fn?.input_params?.parameters && fn.input_params.parameters.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-semibold">Input Parameters</h4>
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
                    {fn.input_params.parameters.map((p) => (
                      <TableRow key={p.name}>
                        <TableCell className="text-muted-foreground tabular-nums">{p.position}</TableCell>
                        <TableCell className="font-medium">{p.name}</TableCell>
                        <TableCell><Badge variant="outline">{p.type_name}</Badge></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}

          {/* Routine definition */}
          {fn?.routine_definition && (
            <div className="space-y-3">
              <h4 className="text-sm font-semibold">Routine Definition</h4>
              <pre className="bg-muted overflow-x-auto rounded-md border p-4 text-sm">
                <code>{fn.routine_definition}</code>
              </pre>
            </div>
          )}
        </UCDetailsLayout>
      </div>

      <UCDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        entityType="function"
        entityName={fullName}
        onConfirm={async () => {
          await deleteFunction(fullName)
          router.push(`${UC_BASE}/schemas/${catalogName}/${schemaName}`)
        }}
      />
    </>
  )
}
