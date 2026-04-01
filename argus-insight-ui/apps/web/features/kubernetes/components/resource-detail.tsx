"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Pencil, Trash2 } from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Separator } from "@workspace/ui/components/separator"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@workspace/ui/components/tabs"
import { Skeleton } from "@workspace/ui/components/skeleton"
import type { K8sResourceItem } from "../types"
import type { DetailTab, ResourceDef } from "../lib/resource-definitions"
import { formatAge } from "../lib/formatters"
import { StatusBadge } from "./status-badge"
import { YamlEditor } from "./yaml-editor"
import { YamlViewer } from "./yaml-viewer"
import { PodLogViewer } from "./pod-log-viewer"
import { EventList } from "./event-list"
import { ResourceDataView } from "./resource-data-view"
import { PodResourceUsage } from "./pod-resource-usage"

interface ResourceDetailProps {
  resourceDef: ResourceDef
  resource: K8sResourceItem | null
  loading: boolean
  error?: string | null
  backUrl: string
  onDelete?: () => Promise<void>
  onUpdate?: (body: object) => Promise<void>
}

export function ResourceDetail({
  resourceDef,
  resource,
  loading,
  error,
  backUrl,
  onDelete,
  onUpdate,
}: ResourceDetailProps) {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<string>("overview")

  if (loading) {
    return (
      <div className="space-y-4 p-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <p className="text-destructive text-sm">{error}</p>
        <Button variant="outline" size="sm" onClick={() => router.push(backUrl)} className="mt-2">
          Go Back
        </Button>
      </div>
    )
  }

  if (!resource) return null

  const metadata = resource.metadata
  const labels = metadata.labels || {}
  const annotations = metadata.annotations || {}

  const tabMap: Record<DetailTab, { label: string; content: React.ReactNode }> = {
    overview: {
      label: "Overview",
      content: (
        <div className="space-y-4">
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Metadata</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <InfoRow label="Name" value={metadata.name} />
              {metadata.namespace && <InfoRow label="Namespace" value={metadata.namespace} />}
              <InfoRow label="UID" value={metadata.uid || ""} mono />
              <InfoRow label="Created" value={`${metadata.creationTimestamp} (${formatAge(metadata.creationTimestamp)})`} />
              {metadata.resourceVersion && (
                <InfoRow label="Resource Version" value={metadata.resourceVersion} mono />
              )}
            </CardContent>
          </Card>

          {Object.keys(labels).length > 0 && (
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">Labels</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(labels).map(([k, v]) => (
                    <Badge key={k} variant="outline" className="text-sm font-[family-name:var(--font-d2coding)]">
                      {k}={v}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {Object.keys(annotations).length > 0 && (
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">Annotations</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {Object.entries(annotations).map(([k, v]) => (
                    <div key={k} className="text-sm font-[family-name:var(--font-d2coding)]">
                      <span className="text-muted-foreground">{k}</span>
                      <span className="mx-1">=</span>
                      <span className="break-all">{v}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {resource.spec && (
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">Spec</CardTitle>
              </CardHeader>
              <CardContent>
                <YamlViewer data={resource.spec} height="400px" />
              </CardContent>
            </Card>
          )}

          {resource.status && (
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">Status</CardTitle>
              </CardHeader>
              <CardContent>
                {renderStatusSection(resource)}
              </CardContent>
            </Card>
          )}

        </div>
      ),
    },
    containers: {
      label: "Containers",
      content: <ContainersTab resource={resource} />,
    },
    conditions: {
      label: "Conditions",
      content: <ConditionsTab resource={resource} />,
    },
    pods: {
      label: "Pods",
      content: (
        <div className="text-sm text-muted-foreground p-4">
          Related pods are shown based on label selectors.
          Navigate to Pods view with the appropriate label filter.
        </div>
      ),
    },
    events: {
      label: "Events",
      content: (
        <EventList
          namespace={metadata.namespace || ""}
          fieldSelector={`involvedObject.name=${metadata.name}`}
        />
      ),
    },
    logs: {
      label: "Logs",
      content: resourceDef.plural === "pods" ? (
        <PodLogViewer
          name={metadata.name}
          namespace={metadata.namespace || "default"}
          containers={getContainerNames(resource)}
        />
      ) : (
        <div className="text-sm text-muted-foreground p-4">
          Logs are only available for Pods.
        </div>
      ),
    },
    data: {
      label: "Data",
      content: <ResourceDataView resource={resource} />,
    },
    rules: {
      label: "Rules",
      content: (
        <YamlViewer data={(resource as Record<string, unknown>).rules || resource.spec} height="400px" />
      ),
    },
    volumes: {
      label: "Volumes",
      content: (
        <YamlViewer data={(resource.spec as Record<string, unknown>)?.volumes || (resource.spec as Record<string, unknown>)?.volumeClaimTemplates} height="300px" />
      ),
    },
    "pod-usage": {
      label: "Pod Resource Usage",
      content: <PodResourceUsage namespace={metadata.name} />,
    },
    yaml: {
      label: "YAML",
      content: (
        <YamlEditor
          resource={resource}
          onSave={onUpdate}
        />
      ),
    },
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => router.push(backUrl)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold">{metadata.name}</h2>
              {metadata.namespace && (
                <Badge variant="outline" className="text-sm">{metadata.namespace}</Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground">{resourceDef.singularLabel}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onDelete && (
            <Button variant="outline" size="sm" className="text-destructive" onClick={onDelete}>
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              Delete
            </Button>
          )}
        </div>
      </div>

      <Separator />

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {resourceDef.detailTabs.map((tab) => {
            const def = tabMap[tab]
            if (!def) return null
            return (
              <TabsTrigger key={tab} value={tab} className="text-sm">
                {def.label}
              </TabsTrigger>
            )
          })}
        </TabsList>
        {resourceDef.detailTabs.map((tab) => {
          const def = tabMap[tab]
          if (!def) return null
          return (
            <TabsContent key={tab} value={tab} className="mt-4">
              {def.content}
            </TabsContent>
          )
        })}
      </Tabs>
    </div>
  )
}

// ── Sub-components ───────────────────────────────────────────────

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-2">
      <span className="text-muted-foreground w-36 shrink-0">{label}:</span>
      <span className={mono ? "font-mono text-sm break-all" : "text-sm break-all"}>{value}</span>
    </div>
  )
}

function renderStatusSection(resource: K8sResourceItem) {
  const status = resource.status as Record<string, unknown> | undefined
  if (!status) return <p className="text-sm text-muted-foreground">No status available</p>

  // Show conditions if available
  const conditions = status.conditions as Array<Record<string, unknown>> | undefined
  if (conditions?.length) {
    return (
      <div className="space-y-2">
        {conditions.map((c, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <StatusBadge status={c.status === "True" ? String(c.type) : `Not${c.type}`} />
            <span className="text-muted-foreground">{String(c.message || c.reason || "")}</span>
          </div>
        ))}
      </div>
    )
  }

  // Fallback: show raw status
  return <YamlViewer data={status} height="300px" />
}

function ContainersTab({ resource }: { resource: K8sResourceItem }) {
  const spec = resource.spec as Record<string, unknown> | undefined
  const containers = spec?.containers as Array<Record<string, unknown>> | undefined
  const initContainers = spec?.initContainers as Array<Record<string, unknown>> | undefined
  const containerStatuses = (resource.status as Record<string, unknown>)?.containerStatuses as Array<Record<string, unknown>> | undefined

  if (!containers?.length) {
    return <p className="text-sm text-muted-foreground p-4">No containers found</p>
  }

  return (
    <div className="space-y-3">
      {initContainers?.length ? (
        <>
          <h4 className="text-sm font-medium text-muted-foreground">Init Containers</h4>
          {initContainers.map((c) => (
            <ContainerCard key={String(c.name)} container={c} />
          ))}
          <h4 className="text-sm font-medium text-muted-foreground mt-4">Containers</h4>
        </>
      ) : null}
      {containers.map((c) => {
        const status = containerStatuses?.find((cs) => cs.name === c.name)
        return <ContainerCard key={String(c.name)} container={c} status={status} />
      })}
    </div>
  )
}

function ContainerCard({
  container,
  status,
}: {
  container: Record<string, unknown>
  status?: Record<string, unknown>
}) {
  const state = status?.state as Record<string, unknown> | undefined
  const stateKey = state ? Object.keys(state)[0] : ""
  const restarts = (status?.restartCount as number) || 0

  return (
    <Card>
      <CardHeader className="py-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-mono">{String(container.name)}</CardTitle>
          {stateKey && <StatusBadge status={stateKey} />}
        </div>
      </CardHeader>
      <CardContent className="text-sm space-y-1">
        <InfoRow label="Image" value={String(container.image || "")} mono />
        {container.ports && (
          <InfoRow
            label="Ports"
            value={(container.ports as Array<Record<string, unknown>>)
              .map((p) => `${p.containerPort}/${p.protocol || "TCP"}`)
              .join(", ")}
          />
        )}
        {restarts > 0 && <InfoRow label="Restarts" value={String(restarts)} />}
        {container.resources && (
          <div className="mt-2">
            <span className="text-muted-foreground">Resources:</span>
            <YamlViewer data={container.resources} height="120px" />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ConditionsTab({ resource }: { resource: K8sResourceItem }) {
  const conditions = (resource.status as Record<string, unknown>)?.conditions as Array<Record<string, unknown>> | undefined
  if (!conditions?.length) {
    return <p className="text-sm text-muted-foreground p-4">No conditions</p>
  }

  return (
    <div className="rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left py-2 px-3 text-sm font-medium">Type</th>
            <th className="text-left py-2 px-3 text-sm font-medium">Status</th>
            <th className="text-left py-2 px-3 text-sm font-medium">Reason</th>
            <th className="text-left py-2 px-3 text-sm font-medium">Message</th>
            <th className="text-left py-2 px-3 text-sm font-medium">Last Transition</th>
          </tr>
        </thead>
        <tbody>
          {conditions.map((c, i) => (
            <tr key={i} className="border-b last:border-b-0">
              <td className="py-2 px-3 font-medium">{String(c.type)}</td>
              <td className="py-2 px-3">
                <StatusBadge status={c.status === "True" ? "Ready" : "NotReady"} />
              </td>
              <td className="py-2 px-3 text-muted-foreground">{String(c.reason || "")}</td>
              <td className="py-2 px-3 text-muted-foreground max-w-[300px] truncate">{String(c.message || "")}</td>
              <td className="py-2 px-3 text-muted-foreground">{formatAge(c.lastTransitionTime as string)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function getContainerNames(resource: K8sResourceItem): string[] {
  const spec = resource.spec as Record<string, unknown> | undefined
  const containers = spec?.containers as Array<Record<string, unknown>> | undefined
  return containers?.map((c) => String(c.name)) || []
}
