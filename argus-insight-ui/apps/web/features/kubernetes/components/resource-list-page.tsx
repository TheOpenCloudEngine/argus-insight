"use client"

import { useState } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { NamespaceSelector } from "./namespace-selector"
import { ResourceTable } from "./resource-table"
import { useK8sResources } from "../hooks/use-k8s-resources"
import { RESOURCE_DEFINITIONS } from "../lib/resource-definitions"

interface ResourceListPageProps {
  resourceType: string
  title?: string
}

/**
 * Generic page component for listing any K8s resource type.
 * Used by all resource pages (pods, deployments, services, etc.)
 */
export function ResourceListPage({ resourceType, title }: ResourceListPageProps) {
  const def = RESOURCE_DEFINITIONS[resourceType]
  const [namespace, setNamespace] = useState<string>("_all")

  const ns = namespace === "_all" ? undefined : namespace
  const { data, loading, error, refetch } = useK8sResources(resourceType, ns)

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

  return (
    <>
      <DashboardHeader title={title || def.pluralLabel}>
        {def.namespaced && (
          <NamespaceSelector value={namespace} onChange={setNamespace} />
        )}
      </DashboardHeader>
      <div className="flex flex-1 flex-col p-4">
        <ResourceTable
          resourceDef={def}
          items={data?.items || []}
          loading={loading}
          error={error}
          namespace={namespace}
          onRefresh={refetch}
        />
      </div>
    </>
  )
}
