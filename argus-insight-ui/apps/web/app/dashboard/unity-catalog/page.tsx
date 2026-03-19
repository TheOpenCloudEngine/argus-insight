"use client"

import { useEffect, useState } from "react"
import { Library, Plus } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { UCEntityTable } from "@/features/unity-catalog/components/uc-entity-table"
import { CreateCatalogDialog } from "@/features/unity-catalog/components/uc-create-catalog-dialog"
import { listCatalogs } from "@/features/unity-catalog/api"
import type { Catalog } from "@/features/unity-catalog/data/schema"

export default function CatalogsListPage() {
  const [catalogs, setCatalogs] = useState<Catalog[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)

  function loadCatalogs() {
    setIsLoading(true)
    listCatalogs().then(setCatalogs).finally(() => setIsLoading(false))
  }

  useEffect(() => { loadCatalogs() }, [])

  return (
    <>
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <p className="text-muted-foreground text-sm">
            Browse and manage Unity Catalog catalogs.
          </p>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> Create Catalog
          </Button>
        </div>
        <UCEntityTable
          data={catalogs}
          isLoading={isLoading}
          emptyMessage="No catalogs found. Create one to get started."
          nameIcon={<Library className="h-4 w-4 text-muted-foreground" />}
          getHref={(c) => `/dashboard/unity-catalog/catalogs/${c.name}`}
        />
      </div>
      <CreateCatalogDialog open={createOpen} onOpenChange={setCreateOpen} onSuccess={loadCatalogs} />
    </>
  )
}
