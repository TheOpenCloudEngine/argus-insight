"use client"

import {
  AlertTriangle,
  CheckCircle2,
  GripVertical,
  Pencil,
  Trash2,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent } from "@workspace/ui/components/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import type { PipelineStep } from "@/features/software-deployment/types"

interface PipelineStepCardProps {
  step: PipelineStep
  index: number
  totalSteps: number
  pipelinePluginNames: string[]
  onToggleEnabled: () => void
  onVersionChange: (version: string) => void
  onEdit: () => void
  onRemove: () => void
  onMoveUp: () => void
  onMoveDown: () => void
}

export function PipelineStepCard({
  step,
  index,
  totalSteps,
  pipelinePluginNames,
  onToggleEnabled,
  onVersionChange,
  onEdit,
  onRemove,
  onMoveUp,
  onMoveDown,
}: PipelineStepCardProps) {
  const plugin = step.plugin
  const selectedVersion = plugin.versions.find(
    (v) => v.version === step.selected_version,
  )

  // Check if all dependencies are satisfied
  const missingDeps = plugin.depends_on.filter(
    (dep) => !pipelinePluginNames.includes(dep),
  )
  const depsOk = missingDeps.length === 0

  return (
    <Card
      className={`transition-opacity ${!step.enabled ? "opacity-50" : ""}`}
    >
      <CardContent className="flex items-center gap-3 py-3 px-4">
        {/* Drag handle / move buttons */}
        <div className="flex flex-col gap-0.5">
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5"
            disabled={index === 0}
            onClick={onMoveUp}
          >
            <GripVertical className="h-3 w-3 rotate-90" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5"
            disabled={index === totalSteps - 1}
            onClick={onMoveDown}
          >
            <GripVertical className="h-3 w-3 rotate-90" />
          </Button>
        </div>

        {/* Enable toggle */}
        <button
          onClick={onToggleEnabled}
          className="flex-shrink-0"
          title={step.enabled ? "Disable step" : "Enable step"}
        >
          {step.enabled ? (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          ) : (
            <div className="h-5 w-5 rounded-full border-2 border-muted-foreground" />
          )}
        </button>

        {/* Step info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground font-mono" style={{ fontSize: 'var(--text-lg)' }}>
              #{index + 1}
            </span>
            <span className="font-medium truncate" style={{ fontSize: 'var(--text-lg)' }}>
              {plugin.display_name}
            </span>
            <Badge variant="outline" className="text-xs">
              {plugin.category}
            </Badge>
            {plugin.source === "external" && (
              <Badge variant="secondary" className="text-xs">
                external
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground truncate mt-0.5">
            {selectedVersion?.description ?? plugin.description}
          </p>
          {/* Dependencies (only show if any) */}
          {plugin.depends_on.length > 0 && (
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-xs text-muted-foreground">Deps:</span>
              {plugin.depends_on.map((dep) => (
                <Badge
                  key={dep}
                  variant={
                    pipelinePluginNames.includes(dep) ? "outline" : "destructive"
                  }
                  className="text-xs py-0"
                >
                  {pipelinePluginNames.includes(dep) ? "✓" : "⚠"} {dep}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Version selector */}
        {plugin.versions.length > 1 ? (
          <Select
            value={step.selected_version}
            onValueChange={onVersionChange}
          >
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {plugin.versions.map((v) => (
                <SelectItem key={v.version} value={v.version}>
                  {v.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Badge variant="outline">v{step.selected_version}</Badge>
        )}

        {/* Dependency warning */}
        {!depsOk && (
          <AlertTriangle className="h-4 w-4 text-destructive flex-shrink-0" />
        )}

        {/* Actions */}
        <div className="flex gap-1 flex-shrink-0">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onEdit}>
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-destructive"
            onClick={onRemove}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
