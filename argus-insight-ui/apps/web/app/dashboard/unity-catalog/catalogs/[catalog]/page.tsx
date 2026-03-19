"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Database, Plus, Trash2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { UCBreadcrumbs } from "@/features/unity-catalog/components/uc-breadcrumbs"
import { UCDescriptionBox } from "@/features/unity-catalog/components/uc-description-box"
import { UCDetailsLayout } from "@/features/unity-catalog/components/uc-details-layout"
import { UCTimestampMetadata } from "@/features/unity-catalog/components/uc-metadata-list"
import { UCEntityTable } from "@/features/unity-catalog/components/uc-entity-table"
import { CreateSchemaDialog } from "@/features/unity-catalog/components/uc-create-schema-dialog"
import { UCDeleteCatalogDialog } from "@/features/unity-catalog/components/uc-delete-catalog-dialog"
import { getCatalog, listSchemas, updateCatalog, deleteCatalog } from "@/features/unity-catalog/api"
import type { Catalog, Schema } from "@/features/unity-catalog/data/schema"

export default function CatalogDetailsPage() {
  const params = useParams<{ catalog: string }>()
  const router = useRouter()
  const catalogName = params.catalog

  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [schemas, setSchemas] = useState<Schema[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [createSchemaOpen, setCreateSchemaOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const isGlobal = catalogName === "global"

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [cat, sch] = await Promise.all([getCatalog(catalogName), listSchemas(catalogName)])
      setCatalog(cat)
      setSchemas(sch)
    } finally {
      setIsLoading(false)
    }
  }, [catalogName])

  useEffect(() => { loadData() }, [loadData])

  if (!catalog && !isLoading) {
    return (
      <div className="p-4">
        <p className="text-muted-foreground">Catalog &apos;{catalogName}&apos; was not found.</p>
      </div>
    )
  }

  return (
    <>
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <UCBreadcrumbs items={[
            { label: "Catalogs", href: "/dashboard/unity-catalog" },
            { label: catalogName },
          ]} />
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => setCreateSchemaOpen(true)}>
              <Plus className="mr-1.5 h-4 w-4" /> Create Schema
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={isGlobal}
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 className="mr-1.5 h-4 w-4" /> Delete Schema
            </Button>
          </div>
        </div>

        <UCDetailsLayout
          sidebar={
            catalog && <UCTimestampMetadata createdAt={catalog.created_at} updatedAt={catalog.updated_at} />
          }
        >
          {catalog && (
            <UCDescriptionBox
              comment={catalog.comment}
              onEdit={async (comment) => {
                await updateCatalog(catalogName, { comment })
                loadData()
              }}
            />
          )}

          <div className="space-y-3">
            <h4 className="text-sm font-semibold">Schemas</h4>
            <UCEntityTable
              data={schemas}
              isLoading={isLoading}
              emptyMessage="No schemas in this catalog."
              nameIcon={<Database className="h-4 w-4 text-muted-foreground" />}
              getHref={(s) => `/dashboard/unity-catalog/schemas/${catalogName}/${s.name}`}
            />
          </div>
        </UCDetailsLayout>
      </div>

      <CreateSchemaDialog
        open={createSchemaOpen}
        onOpenChange={setCreateSchemaOpen}
        catalogName={catalogName}
        onSuccess={loadData}
      />
      <UCDeleteCatalogDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        catalogName={catalogName}
        onConfirm={async () => {
          await deleteCatalog(catalogName)
          router.push("/dashboard/unity-catalog")
        }}
      />
    </>
  )
}
