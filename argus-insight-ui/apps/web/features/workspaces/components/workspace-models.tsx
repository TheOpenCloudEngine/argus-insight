"use client"

import { useCallback, useEffect, useState } from "react"
import {
  AlertCircle,
  Box,
  CheckCircle2,
  Clock,
  Loader2,
  Play,
  Rocket,
  Square,
  XCircle,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import {
  deployModel,
  fetchModelServing,
  fetchWorkspaceModels,
  undeployModel,
} from "@/features/workspaces/api"
import type {
  ModelListResponse,
  ModelServingStatus,
  ModelVersionItem,
  WorkspaceResponse,
} from "@/features/workspaces/types"

// ── Helpers ───────────────────────────────────────────────

function topMetric(metrics: Record<string, number>): string {
  const priority = ["accuracy", "f1", "f1_score", "auc", "rmse", "mse", "mae", "r2"]
  for (const key of priority) {
    if (key in metrics) return `${key}: ${metrics[key].toFixed(4)}`
  }
  const entries = Object.entries(metrics)
  if (entries.length > 0) {
    const [k, v] = entries[0]
    return `${k}: ${typeof v === "number" ? v.toFixed(4) : v}`
  }
  return "—"
}

// ── Deploy Dialog ─────────────────────────────────────────

function DeployDialog({
  open,
  onOpenChange,
  model,
  workspaceId,
  onDeployed,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  model: ModelVersionItem | null
  workspaceId: number
  onDeployed: () => void
}) {
  const [cpu, setCpu] = useState("1")
  const [memory, setMemory] = useState("2Gi")
  const [gpu, setGpu] = useState("0")
  const [minReplicas, setMinReplicas] = useState("0")
  const [maxReplicas, setMaxReplicas] = useState("3")
  const [deploying, setDeploying] = useState(false)

  if (!model) return null

  const handleDeploy = async () => {
    setDeploying(true)
    try {
      await deployModel(workspaceId, {
        model_name: model.name,
        model_version: model.version,
        cpu,
        memory,
        gpu: parseInt(gpu),
        min_replicas: parseInt(minReplicas),
        max_replicas: parseInt(maxReplicas),
      })
      onOpenChange(false)
      onDeployed()
    } catch (e) {
      console.error("Deploy failed:", e)
    } finally {
      setDeploying(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Deploy Model</DialogTitle>
          <DialogDescription>
            Deploy <strong>{model.name}</strong> v{model.version} as a REST API
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="space-y-1">
              <Label className="text-sm">Framework</Label>
              <p className="text-sm text-muted-foreground">{model.framework || "auto"}</p>
            </div>
            <div className="space-y-1">
              <Label className="text-sm">Metric</Label>
              <p className="text-sm text-muted-foreground">{topMetric(model.metrics)}</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-sm">CPU</Label>
              <Select value={cpu} onValueChange={setCpu}>
                <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="0.5">0.5 core</SelectItem>
                  <SelectItem value="1">1 core</SelectItem>
                  <SelectItem value="2">2 cores</SelectItem>
                  <SelectItem value="4">4 cores</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-sm">Memory</Label>
              <Select value={memory} onValueChange={setMemory}>
                <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="512Mi">512Mi</SelectItem>
                  <SelectItem value="1Gi">1Gi</SelectItem>
                  <SelectItem value="2Gi">2Gi</SelectItem>
                  <SelectItem value="4Gi">4Gi</SelectItem>
                  <SelectItem value="8Gi">8Gi</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-sm">GPU</Label>
              <Select value={gpu} onValueChange={setGpu}>
                <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">0</SelectItem>
                  <SelectItem value="1">1</SelectItem>
                  <SelectItem value="2">2</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-sm">Min Replicas</Label>
              <Input value={minReplicas} onChange={(e) => setMinReplicas(e.target.value)} className="h-9 text-sm" />
            </div>
            <div className="space-y-1">
              <Label className="text-sm">Max Replicas</Label>
              <Input value={maxReplicas} onChange={(e) => setMaxReplicas(e.target.value)} className="h-9 text-sm" />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} disabled={deploying}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleDeploy} disabled={deploying}>
              {deploying ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Rocket className="mr-1.5 h-4 w-4" />}
              Deploy
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Main Component ────────────────────────────────────────

interface WorkspaceModelsProps {
  workspace: WorkspaceResponse
  onDeployService: (pluginName: string) => void
}

export function WorkspaceModels({ workspace, onDeployService }: WorkspaceModelsProps) {
  const [data, setData] = useState<ModelListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [servingStatuses, setServingStatuses] = useState<Record<string, ModelServingStatus>>({})
  const [deployTarget, setDeployTarget] = useState<ModelVersionItem | null>(null)
  const [deployOpen, setDeployOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await fetchWorkspaceModels(workspace.id)
      setData(result)

      // Fetch serving status for each model
      const statuses: Record<string, ModelServingStatus> = {}
      for (const model of result.models) {
        try {
          const s = await fetchModelServing(workspace.id, model.name)
          if (s.status !== "Not deployed") {
            statuses[model.name] = s
          }
        } catch { /* ignore */ }
      }
      setServingStatuses(statuses)
    } catch (e) {
      console.error("Failed to load models:", e)
    } finally {
      setLoading(false)
    }
  }, [workspace.id])

  useEffect(() => { load() }, [load])

  const handleUndeploy = async (modelName: string) => {
    try {
      await undeployModel(workspace.id, modelName)
      await load()
    } catch (e) {
      console.error("Undeploy failed:", e)
    }
  }

  // MLflow not available
  if (data && !data.mlflow_available) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Models</CardTitle>
        </CardHeader>
        <CardContent className="text-center py-8">
          <Box className="mx-auto h-8 w-8 text-muted-foreground mb-3" />
          <p className="text-sm text-muted-foreground mb-3">
            MLflow is required to manage models.
          </p>
          <Button size="sm" onClick={() => onDeployService("argus-mlflow")}>
            <Rocket className="mr-1.5 h-4 w-4" /> Deploy MLflow
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (loading) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Models</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  const models = data?.models ?? []
  const kserveAvailable = data?.kserve_available ?? false

  return (
    <>
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Models ({models.length})</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {models.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              No models registered in MLflow yet. Train a model in Jupyter and log it with <code className="bg-muted px-1 rounded">mlflow.log_model()</code>.
            </div>
          ) : (
            <div className="max-h-[300px] overflow-auto">
              <table className="w-full">
                <thead className="sticky top-0 z-10">
                  <tr className="border-b bg-muted/30 text-sm text-muted-foreground">
                    <th className="px-4 py-1 text-left font-medium">Model</th>
                    <th className="px-4 py-1 text-left font-medium">Version</th>
                    <th className="px-4 py-1 text-left font-medium">Framework</th>
                    <th className="px-4 py-1 text-left font-medium">Metric</th>
                    <th className="px-4 py-1 text-left font-medium">Serving</th>
                    <th className="px-4 py-1 text-right font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {models.map((m) => {
                    const serving = servingStatuses[m.name]
                    return (
                      <tr key={`${m.name}-${m.version}`} className="border-b last:border-b-0">
                        <td className="px-4 py-1.5 font-medium">{m.name}</td>
                        <td className="px-4 py-1.5">v{m.version}</td>
                        <td className="px-4 py-1.5 text-muted-foreground">{m.framework || "—"}</td>
                        <td className="px-4 py-1.5 font-mono text-xs">{topMetric(m.metrics)}</td>
                        <td className="px-4 py-1.5">
                          {serving?.ready ? (
                            <Badge className="bg-green-100 text-green-800 text-[10px]">
                              <CheckCircle2 className="mr-1 h-3 w-3" />Serving
                            </Badge>
                          ) : serving ? (
                            <Badge className="bg-yellow-100 text-yellow-800 text-[10px]">
                              <Clock className="mr-1 h-3 w-3" />{serving.status}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-4 py-1.5 text-right">
                          {serving && serving.status !== "Not deployed" ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs text-destructive"
                              onClick={() => handleUndeploy(m.name)}
                            >
                              <Square className="mr-1 h-3 w-3" /> Undeploy
                            </Button>
                          ) : kserveAvailable ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs"
                              onClick={() => { setDeployTarget(m); setDeployOpen(true) }}
                            >
                              <Play className="mr-1 h-3 w-3" /> Deploy
                            </Button>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs"
                              onClick={() => onDeployService("argus-kserve")}
                            >
                              <AlertCircle className="mr-1 h-3 w-3" /> Need KServe
                            </Button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <DeployDialog
        open={deployOpen}
        onOpenChange={setDeployOpen}
        model={deployTarget}
        workspaceId={workspace.id}
        onDeployed={load}
      />
    </>
  )
}
