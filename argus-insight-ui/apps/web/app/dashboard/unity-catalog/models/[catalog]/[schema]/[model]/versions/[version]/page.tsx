"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Badge } from "@workspace/ui/components/badge"

import { UCBreadcrumbs } from "@/features/unity-catalog/components/uc-breadcrumbs"
import { UCDescriptionBox } from "@/features/unity-catalog/components/uc-description-box"
import { UCDetailsLayout } from "@/features/unity-catalog/components/uc-details-layout"
import { UCTimestampMetadata, UCMetadataList } from "@/features/unity-catalog/components/uc-metadata-list"
import { getModelVersion, updateModelVersion } from "@/features/unity-catalog/api"
import type { ModelVersion } from "@/features/unity-catalog/data/schema"

const statusColors: Record<string, string> = {
  READY: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  PENDING_REGISTRATION: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  FAILED_REGISTRATION: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
}

export default function ModelVersionDetailsPage() {
  const params = useParams<{ catalog: string; schema: string; model: string; version: string }>()
  const { catalog: catalogName, schema: schemaName, model: modelName, version: versionStr } = params
  const versionNum = Number(versionStr)
  const fullModelName = `${catalogName}.${schemaName}.${modelName}`
  const UC_BASE = "/dashboard/unity-catalog"

  const [version, setVersion] = useState<ModelVersion | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      setVersion(await getModelVersion(fullModelName, versionNum))
    } finally {
      setIsLoading(false)
    }
  }, [fullModelName, versionNum])

  useEffect(() => { loadData() }, [loadData])

  return (
    <>
      <div className="flex flex-1 flex-col gap-4 p-4">
        <UCBreadcrumbs items={[
          { label: "Catalogs", href: UC_BASE },
          { label: catalogName, href: `${UC_BASE}/catalogs/${catalogName}` },
          { label: schemaName, href: `${UC_BASE}/schemas/${catalogName}/${schemaName}` },
          { label: modelName, href: `${UC_BASE}/models/${catalogName}/${schemaName}/${modelName}` },
          { label: `v${versionStr}` },
        ]} />

        <UCDetailsLayout
          sidebar={
            version && <UCTimestampMetadata createdAt={version.created_at} updatedAt={version.updated_at} />
          }
        >
          {version && (
            <UCDescriptionBox
              comment={version.comment}
              onEdit={async (comment) => {
                await updateModelVersion(fullModelName, versionNum, { comment })
                loadData()
              }}
            />
          )}

          {version && (
            <div className="space-y-3">
              <h4 className="text-sm font-semibold">Version Details</h4>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-md border p-3">
                  <p className="text-muted-foreground text-xs">Status</p>
                  <Badge variant="outline" className={statusColors[version.status ?? ""] ?? ""}>
                    {version.status ?? "—"}
                  </Badge>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-muted-foreground text-xs">Version</p>
                  <p className="text-sm font-medium">v{version.version}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-muted-foreground text-xs">Source</p>
                  <p className="truncate text-sm font-mono">{version.source ?? "—"}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-muted-foreground text-xs">Run ID</p>
                  <p className="truncate text-sm font-mono">{version.run_id ?? "—"}</p>
                </div>
              </div>
            </div>
          )}
        </UCDetailsLayout>
      </div>
    </>
  )
}
