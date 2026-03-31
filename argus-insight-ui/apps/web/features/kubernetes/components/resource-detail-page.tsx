"use client"

import { useSearchParams } from "next/navigation"
import { DashboardHeader } from "@/components/dashboard-header"
import { ResourceDetail } from "./resource-detail"
import { useK8sResource } from "../hooks/use-k8s-resources"
import { RESOURCE_DEFINITIONS, RESOURCE_URL_MAP } from "../lib/resource-definitions"
import * as api from "../api"

interface ResourceDetailPageProps {
  resourceType: string
  name: string
}

/**
 * Generic page component for displaying a single K8s resource detail.
 */
export function ResourceDetailPage({ resourceType, name }: ResourceDetailPageProps) {
  const searchParams = useSearchParams()
  const namespace = searchParams.get("namespace") || undefined
  const def = RESOURCE_DEFINITIONS[resourceType]
  const backUrl = RESOURCE_URL_MAP[resourceType] || "/dashboard/kubernetes"

  const { data, loading, error, refetch } = useK8sResource(resourceType, name, namespace)

  if (!def) {
    return (
      <>
        <DashboardHeader title="Unknown Resource" />
        <div className="p-4">
          <p className="text-sm text-muted-foreground">Unknown resource type: {resourceType}</p>
        </div>
      </>
    )
  }

  const handleDelete = async () => {
    if (!confirm(`Delete ${def.singularLabel} "${name}"?`)) return
    await api.deleteResource(resourceType, name, namespace)
    window.location.href = backUrl
  }

  const handleUpdate = async (body: object) => {
    await api.updateResource(resourceType, name, body, namespace)
    refetch()
  }

  return (
    <>
      <DashboardHeader title={`${def.singularLabel}: ${name}`} />
      <div className="flex flex-1 flex-col p-4">
        <ResourceDetail
          resourceDef={def}
          resource={data}
          loading={loading}
          error={error}
          backUrl={backUrl}
          onDelete={handleDelete}
          onUpdate={handleUpdate}
        />
      </div>
    </>
  )
}
