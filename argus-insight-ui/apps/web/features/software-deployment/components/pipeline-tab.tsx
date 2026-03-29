"use client"

import { useCallback, useState } from "react"
import {
  AlertTriangle,
  ArrowDown,
  CheckCircle2,
  Loader2,
  Plus,
  Save,
  ShieldCheck,
} from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Separator } from "@workspace/ui/components/separator"

import type {
  PipelineResponse,
  PipelineStep,
  PluginResponse,
} from "@/features/software-deployment/types"
import { useAuth } from "@/features/auth"
import {
  createPipeline,
  updatePipeline,
  validatePluginOrder,
} from "@/features/software-deployment/api"
import { PipelineStepCard } from "./pipeline-step-card"
import { PipelineStepEditSheet } from "./pipeline-step-edit-sheet"
import { AddStepDialog } from "./add-step-dialog"
import { PipelinesGrid } from "./pipelines-grid"

interface PipelineTabProps {
  plugins: PluginResponse[]
  onRefresh: () => void
}

function generatePipelineId(): string {
  const now = new Date()
  const date =
    String(now.getFullYear()) +
    String(now.getMonth() + 1).padStart(2, "0") +
    String(now.getDate()).padStart(2, "0")
  const time =
    String(now.getHours()).padStart(2, "0") +
    String(now.getMinutes()).padStart(2, "0") +
    String(now.getSeconds()).padStart(2, "0")
  const hex = Math.random().toString(16).slice(2, 6)
  return `pipeline-${date}-${time}-${hex}`
}

function buildPipelineFromPlugins(plugins: PluginResponse[]): PipelineStep[] {
  const configured = plugins
    .filter((p) => p.display_order !== null)
    .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))

  return configured.map((p, i) => ({
    plugin_name: p.name,
    plugin: p,
    enabled: p.enabled ?? true,
    display_order: i,
    selected_version: p.selected_version ?? p.default_version,
    config: {},
  }))
}

function buildPipelineFromSaved(
  saved: PipelineResponse,
  plugins: PluginResponse[],
): PipelineStep[] {
  const pluginMap = new Map(plugins.map((p) => [p.name, p]))
  return saved.plugins
    .sort((a, b) => a.display_order - b.display_order)
    .filter((item) => pluginMap.has(item.plugin_name))
    .map((item, i) => ({
      plugin_name: item.plugin_name,
      plugin: pluginMap.get(item.plugin_name)!,
      enabled: item.enabled,
      display_order: i,
      selected_version: item.selected_version ?? pluginMap.get(item.plugin_name)!.default_version,
      config: (item.default_config as Record<string, unknown>) ?? {},
    }))
}

export function PipelineTab({ plugins, onRefresh }: PipelineTabProps) {
  const { user } = useAuth()
  const [steps, setSteps] = useState<PipelineStep[]>([])
  const [saving, setSaving] = useState(false)
  const [validating, setValidating] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error" | "warning"
    text: string
  } | null>(null)
  const [editStep, setEditStep] = useState<PipelineStep | null>(null)
  const [editSheetOpen, setEditSheetOpen] = useState(false)
  const [addDialogOpen, setAddDialogOpen] = useState(false)

  // Save Pipeline dialog
  const [saveDialogOpen, setSaveDialogOpen] = useState(false)
  const [saveName, setSaveName] = useState("")
  const [saveDisplayName, setSaveDisplayName] = useState("")
  const [saveDescription, setSaveDescription] = useState("")

  // Pipeline grid refresh key
  const [gridRefreshKey, setGridRefreshKey] = useState(0)

  // Currently loaded pipeline (null = new pipeline)
  const [loadedPipeline, setLoadedPipeline] = useState<PipelineResponse | null>(null)

  // Whether the editor panel is visible (true when creating new or selected existing)
  const [editorOpen, setEditorOpen] = useState(false)

  const pipelinePluginNames = steps.map((s) => s.plugin_name)
  const enabledStepNames = steps
    .filter((s) => s.enabled)
    .map((s) => s.plugin_name)

  function showStatus(
    type: "success" | "error" | "warning",
    text: string,
    timeout = 5000,
  ) {
    setStatusMessage({ type, text })
    if (timeout > 0) setTimeout(() => setStatusMessage(null), timeout)
  }

  // --- Step mutations ---

  const handleToggleEnabled = useCallback((index: number) => {
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, enabled: !s.enabled } : s)),
    )
  }, [])

  const handleVersionChange = useCallback(
    (index: number, version: string) => {
      setSteps((prev) =>
        prev.map((s, i) =>
          i === index ? { ...s, selected_version: version } : s,
        ),
      )
    },
    [],
  )

  const handleMoveUp = useCallback((index: number) => {
    if (index === 0) return
    setSteps((prev) => {
      const next = [...prev]
      ;[next[index - 1], next[index]] = [next[index]!, next[index - 1]!]
      return next.map((s, i) => ({ ...s, display_order: i }))
    })
  }, [])

  const handleMoveDown = useCallback((index: number) => {
    setSteps((prev) => {
      if (index >= prev.length - 1) return prev
      const next = [...prev]
      ;[next[index], next[index + 1]] = [next[index + 1]!, next[index]!]
      return next.map((s, i) => ({ ...s, display_order: i }))
    })
  }, [])

  const handleRemove = useCallback((index: number) => {
    setSteps((prev) =>
      prev
        .filter((_, i) => i !== index)
        .map((s, i) => ({ ...s, display_order: i })),
    )
  }, [])

  const handleEdit = useCallback((step: PipelineStep) => {
    setEditStep(step)
    setEditSheetOpen(true)
  }, [])

  const handleApplyEdit = useCallback((updated: PipelineStep) => {
    setSteps((prev) =>
      prev.map((s) =>
        s.plugin_name === updated.plugin_name ? updated : s,
      ),
    )
    setEditSheetOpen(false)
  }, [])

  const handleAddPlugin = useCallback(
    (plugin: PluginResponse) => {
      const newStep: PipelineStep = {
        plugin_name: plugin.name,
        plugin,
        enabled: true,
        display_order: steps.length,
        selected_version: plugin.selected_version ?? plugin.default_version,
        config: {},
      }
      setSteps((prev) => [...prev, newStep])
      setAddDialogOpen(false)
    },
    [steps.length],
  )

  // --- Load saved pipeline ---

  const handleSelectPipeline = useCallback(
    (pipeline: PipelineResponse) => {
      setSteps(buildPipelineFromSaved(pipeline, plugins))
      setLoadedPipeline(pipeline)
      setEditorOpen(true)
    },
    [plugins],
  )

  // --- Pipeline deleted from grid ---

  const handlePipelineDeleted = useCallback(
    (pipelineId: number) => {
      if (loadedPipeline && loadedPipeline.id === pipelineId) {
        setLoadedPipeline(null)
        setSteps([])
        setEditorOpen(false)
        setStatusMessage(null)
      }
    },
    [loadedPipeline],
  )

  // --- New Pipeline ---

  const handleNewPipeline = () => {
    setLoadedPipeline(null)
    setSteps([])
    setEditorOpen(true)
    setStatusMessage(null)
  }

  // --- Validate ---

  const handleValidate = async () => {
    setValidating(true)
    setStatusMessage(null)
    try {
      const versions: Record<string, string> = {}
      for (const s of steps) {
        if (s.enabled) versions[s.plugin_name] = s.selected_version
      }
      const result = await validatePluginOrder(enabledStepNames, versions)
      if (result.valid) {
        showStatus(
          "success",
          "All dependencies satisfied. Pipeline order is valid.",
        )
      } else {
        showStatus(
          "warning",
          `Dependency violations:\n${result.violations.join("\n")}`,
          0,
        )
      }
    } catch (err) {
      showStatus(
        "error",
        err instanceof Error ? err.message : "Validation failed",
      )
    } finally {
      setValidating(false)
    }
  }

  // --- Save Pipeline ---

  function buildOrderItems() {
    return steps.map((s, i) => ({
      plugin_name: s.plugin_name,
      enabled: s.enabled,
      display_order: i,
      selected_version: s.selected_version,
      default_config:
        Object.keys(s.config).length > 0 ? s.config : null,
    }))
  }

  const handleSaveClick = () => {
    if (loadedPipeline) {
      // Existing pipeline — pre-fill with current values
      setSaveName(loadedPipeline.name)
      setSaveDisplayName(loadedPipeline.display_name)
      setSaveDescription(loadedPipeline.description ?? "")
    } else {
      // New pipeline
      setSaveName(generatePipelineId())
      setSaveDisplayName("")
      setSaveDescription("")
    }
    setSaveDialogOpen(true)
  }

  const handleSaveConfirm = async () => {
    if (!saveDisplayName.trim()) return
    setSaving(true)
    setStatusMessage(null)
    try {
      const orderItems = buildOrderItems()

      if (loadedPipeline) {
        // Update existing pipeline (version auto-incremented by backend)
        const updated = await updatePipeline(loadedPipeline.id, {
          display_name: saveDisplayName.trim(),
          description: saveDescription.trim() || undefined,
          plugins: orderItems,
        })
        setLoadedPipeline(updated)
        showStatus("success", `Pipeline "${saveDisplayName}" updated (v${updated.version}).`)
      } else {
        // Create new pipeline
        const created = await createPipeline({
          name: saveName.trim(),
          display_name: saveDisplayName.trim(),
          description: saveDescription.trim() || undefined,
          created_by: user?.username,
          plugins: orderItems,
        })
        setLoadedPipeline(created)
        showStatus("success", `Pipeline "${saveDisplayName}" saved successfully.`)
      }

      setSaveDialogOpen(false)
      setGridRefreshKey((k) => k + 1)
      setLoadedPipeline(null)
      setSteps([])
      setEditorOpen(false)
      setStatusMessage(null)
      onRefresh()
    } catch (err) {
      showStatus(
        "error",
        err instanceof Error ? err.message : "Failed to save pipeline",
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button onClick={handleNewPipeline}>
          <Plus className="h-4 w-4 mr-1.5" />
          New Pipeline
        </Button>
      </div>
      <PipelinesGrid
        onSelect={handleSelectPipeline}
        onDeleted={handlePipelineDeleted}
        refreshKey={gridRefreshKey}
      />

      {editorOpen && (
        <>
      <Separator />

      {/* Deployment Pipeline Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">
            {loadedPipeline ? loadedPipeline.display_name : "New Pipeline"}
          </h3>
          <p className="text-sm text-muted-foreground">
            {loadedPipeline?.description || "Add steps to build your deployment pipeline."}
          </p>
        </div>
        <Button onClick={() => setAddDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-1.5" />
          Add Step
        </Button>
      </div>

      {/* Pipeline steps */}
      {steps.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <p>No steps in the pipeline.</p>
            <p className="text-sm">
              Click &quot;Add Step&quot; to get started.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {steps.map((step, index) => (
            <div key={step.plugin_name}>
              <PipelineStepCard
                step={step}
                index={index}
                totalSteps={steps.length}
                pipelinePluginNames={pipelinePluginNames}
                onToggleEnabled={() => handleToggleEnabled(index)}
                onVersionChange={(v) => handleVersionChange(index, v)}
                onEdit={() => handleEdit(step)}
                onRemove={() => handleRemove(index)}
                onMoveUp={() => handleMoveUp(index)}
                onMoveDown={() => handleMoveDown(index)}
              />
              {index < steps.length - 1 && (
                <div className="flex justify-center py-1">
                  <ArrowDown className="h-4 w-4 text-muted-foreground" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Status message */}
      {statusMessage && (
        <Card
          className={
            statusMessage.type === "success"
              ? "border-green-500 bg-green-50 dark:bg-green-950/20"
              : statusMessage.type === "warning"
                ? "border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20"
                : "border-destructive bg-destructive/10"
          }
        >
          <CardContent className="flex items-start gap-2 py-3">
            {statusMessage.type === "success" ? (
              <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5 shrink-0" />
            )}
            <pre className="text-sm whitespace-pre-wrap">
              {statusMessage.text}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      {steps.length > 0 && (
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={handleValidate}
            disabled={validating}
          >
            {validating ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <ShieldCheck className="h-4 w-4 mr-1.5" />
            )}
            Validate Order
          </Button>
          <Button onClick={handleSaveClick} disabled={saving}>
            {saving ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1.5" />
            )}
            Save Pipeline
          </Button>
        </div>
      )}
        </>
      )}

      {/* Save Pipeline Dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {loadedPipeline ? "Update Pipeline" : "Save Pipeline"}
            </DialogTitle>
            <DialogDescription>
              {loadedPipeline
                ? `Update "${loadedPipeline.display_name}" (v${loadedPipeline.version} → v${(loadedPipeline.version ?? 0) + 1}).`
                : "Give this pipeline a name to save it for later use."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="pipeline-display-name">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="pipeline-display-name"
                placeholder="e.g., ML Team Pipeline"
                value={saveDisplayName}
                onChange={(e) => setSaveDisplayName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pipeline-description">Description</Label>
              <Input
                id="pipeline-description"
                placeholder="Optional description"
                value={saveDescription}
                onChange={(e) => setSaveDescription(e.target.value)}
              />
            </div>
            <div className="text-sm text-muted-foreground">
              {steps.filter((s) => s.enabled).length} enabled steps will be
              saved.
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setSaveDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveConfirm}
              disabled={saving || !saveDisplayName.trim()}
            >
              {saving ? (
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-1.5" />
              )}
              Save
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Sheet */}
      <PipelineStepEditSheet
        open={editSheetOpen}
        onOpenChange={setEditSheetOpen}
        step={editStep}
        onApply={handleApplyEdit}
      />

      {/* Add Dialog */}
      <AddStepDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        allPlugins={plugins}
        pipelinePluginNames={pipelinePluginNames}
        onAdd={handleAddPlugin}
      />
    </div>
  )
}
