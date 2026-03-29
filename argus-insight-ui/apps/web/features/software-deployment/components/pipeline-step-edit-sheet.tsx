"use client"

import { useEffect, useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@workspace/ui/components/sheet"
import { Button } from "@workspace/ui/components/button"
import { Badge } from "@workspace/ui/components/badge"
import { Label } from "@workspace/ui/components/label"
import { Separator } from "@workspace/ui/components/separator"
import { Loader2 } from "lucide-react"
import type { PipelineStep, JsonSchema } from "@/features/software-deployment/types"
import { fetchPluginVersionSchema } from "@/features/software-deployment/api"
import { DynamicConfigForm } from "@/features/software-deployment/components/dynamic-config-form"

interface PipelineStepEditSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  step: PipelineStep | null
  onApply: (step: PipelineStep) => void
}

export function PipelineStepEditSheet({
  open,
  onOpenChange,
  step,
  onApply,
}: PipelineStepEditSheetProps) {
  const [selectedVersion, setSelectedVersion] = useState("")
  const [localConfig, setLocalConfig] = useState<Record<string, unknown>>({})
  const [schema, setSchema] = useState<JsonSchema | null | undefined>(undefined)
  const [loadingSchema, setLoadingSchema] = useState(false)

  // Reset local state when step changes
  useEffect(() => {
    if (step) {
      setSelectedVersion(step.selected_version)
      setLocalConfig({ ...step.config })
      setSchema(undefined)
    }
  }, [step])

  // Load schema when sheet opens or version changes
  useEffect(() => {
    if (!open || !step || !selectedVersion) return

    let cancelled = false
    setLoadingSchema(true)
    setSchema(undefined)

    fetchPluginVersionSchema(step.plugin_name, selectedVersion)
      .then((result) => {
        if (!cancelled) {
          setSchema(result)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSchema(null)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingSchema(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [open, step, selectedVersion])

  if (!step) return null

  const versionInfo = step.plugin.versions.find(
    (v) => v.version === selectedVersion,
  )

  function handleApply() {
    onApply({
      ...step!,
      selected_version: selectedVersion,
      config: { ...localConfig },
    })
    onOpenChange(false)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto px-6" style={{ maxWidth: 700 }}>
        <SheetHeader className="px-0">
          <SheetTitle className="text-xl">
            {step.plugin.display_name} &mdash; Step Configuration
          </SheetTitle>
          <SheetDescription>
            Configure version and settings for this pipeline step.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-6 py-6">
          {/* Version (read-only, single line) */}
          <p className="text-sm">
            <Label className="mr-2 inline">Version</Label>
            <span className="font-medium">{versionInfo?.display_name ?? selectedVersion}</span>
            {versionInfo?.release_date && (
              <span className="text-muted-foreground ml-2">Released {versionInfo.release_date}</span>
            )}
            {step.plugin_name.startsWith("argus-") ? (
              <Badge className="ml-2 text-xs bg-blue-600 text-white hover:bg-blue-600">BUILT-IN</Badge>
            ) : (
              <Badge className="ml-2 text-xs bg-orange-500 text-white hover:bg-orange-500">CUSTOM</Badge>
            )}
          </p>

          {/* Changelog */}
          {versionInfo?.changelog && (
            <div className="space-y-2">
              <Label>Changelog</Label>
              <pre className="text-muted-foreground whitespace-pre-wrap rounded-md border bg-muted/50 p-3 text-sm" style={{ fontFamily: "'D2Coding', monospace" }}>
                {versionInfo.changelog}
              </pre>
            </div>
          )}

          <Separator />

          {/* Configuration */}
          <div className="space-y-3">
            <Label>Configuration</Label>
            {loadingSchema && (
              <div className="flex items-center gap-2 text-muted-foreground text-sm py-4">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading configuration schema...
              </div>
            )}
            {!loadingSchema && schema && (
              <DynamicConfigForm
                schema={schema}
                values={localConfig}
                onChange={setLocalConfig}
              />
            )}
            {!loadingSchema && schema === null && (
              <p className="text-muted-foreground text-sm py-2">
                No configurable settings for this version.
              </p>
            )}
          </div>

          <Separator />

          {/* Dependencies */}
          {step.plugin.depends_on.length > 0 && (
            <div className="space-y-2">
              <Label>Dependencies</Label>
              <div className="flex flex-wrap gap-1">
                {step.plugin.depends_on.map((dep) => (
                  <Badge key={dep} variant="outline">
                    {dep}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="flex justify-end pt-4">
            <Button onClick={handleApply}>Apply Changes</Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
