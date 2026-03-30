"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, Loader2 } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { authFetch } from "@/features/auth/auth-fetch"
import { PluginIcon } from "@/features/software-deployment/components/plugin-icon"

interface MappingItem {
  service_key: string
  service_label: string
  icon: string
  pipeline_id: number | null
  pipeline_name: string | null
}

interface PipelineOption {
  id: number
  name: string
  display_name: string
}

export function DeployMappingTab() {
  const [mappings, setMappings] = useState<MappingItem[]>([])
  const [pipelines, setPipelines] = useState<PipelineOption[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<Record<string, boolean>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})
  // Track local edits per service
  const [edits, setEdits] = useState<Record<string, string>>({})

  useEffect(() => {
    async function load() {
      try {
        const [mappingRes, pipelineRes] = await Promise.all([
          authFetch("/api/v1/settings/deploy-mapping"),
          authFetch("/api/v1/plugins/pipelines"),
        ])
        if (mappingRes.ok) {
          const data = await mappingRes.json()
          setMappings(data.mappings ?? [])
        }
        if (pipelineRes.ok) {
          const data = await pipelineRes.json()
          setPipelines(data.items ?? [])
        }
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSelect = (serviceKey: string, value: string) => {
    setEdits((prev) => ({ ...prev, [serviceKey]: value }))
    setSaved((prev) => ({ ...prev, [serviceKey]: false }))
  }

  const handleSave = async (serviceKey: string) => {
    const selectedValue = edits[serviceKey]
    const pipelineId =
      selectedValue !== undefined
        ? selectedValue === "none"
          ? null
          : parseInt(selectedValue)
        : mappings.find((m) => m.service_key === serviceKey)?.pipeline_id ?? null

    setSaving((prev) => ({ ...prev, [serviceKey]: true }))
    try {
      const res = await authFetch(`/api/v1/settings/deploy-mapping/${serviceKey}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pipeline_id: pipelineId }),
      })
      if (res.ok) {
        // Update local state
        setMappings((prev) =>
          prev.map((m) =>
            m.service_key === serviceKey
              ? {
                  ...m,
                  pipeline_id: pipelineId,
                  pipeline_name:
                    pipelines.find((p) => p.id === pipelineId)?.display_name ?? null,
                }
              : m,
          ),
        )
        setSaved((prev) => ({ ...prev, [serviceKey]: true }))
        setTimeout(() => setSaved((prev) => ({ ...prev, [serviceKey]: false })), 2000)
      }
    } catch {
      // ignore
    } finally {
      setSaving((prev) => ({ ...prev, [serviceKey]: false }))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Map each service to a pipeline. When users add a service from the Workspace
        page, the mapped pipeline will be executed automatically.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {mappings.map((m) => {
          const currentValue =
            edits[m.service_key] !== undefined
              ? edits[m.service_key]
              : m.pipeline_id
                ? String(m.pipeline_id)
                : "none"

          return (
            <Card key={m.service_key}>
              <CardHeader className="flex flex-row items-center gap-3 pb-3">
                <PluginIcon icon={m.icon} size={32} className="shrink-0 rounded" />
                <CardTitle className="text-sm">{m.service_label}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Select
                  value={currentValue}
                  onValueChange={(v) => handleSelect(m.service_key, v)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select pipeline..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">
                      <span className="text-muted-foreground">No pipeline</span>
                    </SelectItem>
                    {pipelines.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.display_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <div className="flex items-center justify-end gap-2">
                  {saved[m.service_key] && (
                    <span className="flex items-center gap-1 text-xs text-green-600">
                      <CheckCircle2 className="h-3 w-3" />
                      Saved
                    </span>
                  )}
                  <Button
                    size="sm"
                    className="text-xs"
                    onClick={() => handleSave(m.service_key)}
                    disabled={saving[m.service_key]}
                  >
                    {saving[m.service_key] ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : null}
                    Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {pipelines.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-4">
          No pipelines available. Create pipelines in the Pipeline tab first.
        </p>
      )}
    </div>
  )
}
