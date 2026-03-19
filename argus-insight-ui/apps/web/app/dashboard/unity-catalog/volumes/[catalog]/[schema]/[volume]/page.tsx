"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { HardDrive, MoreHorizontal, Trash2 } from "lucide-react"

import { DashboardHeader } from "@/components/dashboard-header"
import { Button } from "@workspace/ui/components/button"
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
import { getVolume, updateVolume, deleteVolume } from "@/features/unity-catalog/api"
import type { Volume } from "@/features/unity-catalog/data/schema"

export default function VolumeDetailsPage() {
  const params = useParams<{ catalog: string; schema: string; volume: string }>()
  const router = useRouter()
  const { catalog: catalogName, schema: schemaName, volume: volumeName } = params
  const fullName = `${catalogName}.${schemaName}.${volumeName}`
  const UC_BASE = "/dashboard/unity-catalog"

  const [volume, setVolume] = useState<Volume | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      setVolume(await getVolume(fullName))
    } finally {
      setIsLoading(false)
    }
  }, [fullName])

  useEffect(() => { loadData() }, [loadData])

  return (
    <>
      <DashboardHeader title={fullName} />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <UCBreadcrumbs items={[
            { label: "Catalogs", href: UC_BASE },
            { label: catalogName, href: `${UC_BASE}/catalogs/${catalogName}` },
            { label: schemaName, href: `${UC_BASE}/schemas/${catalogName}/${schemaName}` },
            { label: volumeName },
          ]} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem className="text-destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 className="mr-2 h-4 w-4" /> Delete Volume
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <UCDetailsLayout
          sidebar={
            volume && (
              <div className="space-y-6">
                <UCMetadataList
                  title="Volume details"
                  items={[
                    { label: "Volume type", value: volume.volume_type },
                    { label: "Storage location", value: volume.storage_location },
                  ]}
                />
                <UCTimestampMetadata createdAt={volume.created_at} updatedAt={volume.updated_at} />
              </div>
            )
          }
        >
          {volume && (
            <UCDescriptionBox
              comment={volume.comment}
              onEdit={async (comment) => {
                await updateVolume(fullName, { comment })
                loadData()
              }}
            />
          )}
        </UCDetailsLayout>
      </div>

      <UCDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        entityType="volume"
        entityName={fullName}
        onConfirm={async () => {
          await deleteVolume(fullName)
          router.push(`${UC_BASE}/schemas/${catalogName}/${schemaName}`)
        }}
      />
    </>
  )
}
