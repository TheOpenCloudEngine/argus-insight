"use client"

import { useCallback, useEffect, useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@workspace/ui/components/dialog"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Textarea } from "@workspace/ui/components/textarea"
import { Badge } from "@workspace/ui/components/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@workspace/ui/components/command"
import { Popover, PopoverContent, PopoverTrigger } from "@workspace/ui/components/popover"
import { Separator } from "@workspace/ui/components/separator"
import { ArrowDown, ArrowUp, ArrowRight, Plus, Trash2, Check, ChevronsUpDown } from "lucide-react"
import { authFetch } from "@/features/auth/auth-fetch"

const BASE = "/api/v1/catalog"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Platform = {
  id: number
  platform_id: string
  name: string
  type: string
}

type DatasetSummary = {
  id: number
  urn: string
  name: string
  platform_name: string
  platform_type: string
}

type SchemaField = {
  id: number
  field_path: string
  field_type: string
}

type PipelineSummary = {
  id: number
  pipeline_name: string
  pipeline_type: string
}

type ColumnMapping = {
  source_column: string
  target_column: string
  transform_type: string
  transform_expr: string
}

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  datasetId: number
  datasetName: string
  onCreated: () => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LineageAddDialog({
  open,
  onOpenChange,
  datasetId,
  datasetName,
  onCreated,
}: Props) {
  const [step, setStep] = useState(1)

  // Step 1: Direction
  const [direction, setDirection] = useState<"source" | "target">("source")

  // Step 2: Dataset selection
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [selectedPlatformId, setSelectedPlatformId] = useState<string>("all")
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null)
  const [relationType, setRelationType] = useState("ETL")
  const [pipelines, setPipelines] = useState<PipelineSummary[]>([])
  const [selectedPipelineId, setSelectedPipelineId] = useState<string>("none")
  const [description, setDescription] = useState("")
  const [datasetPopoverOpen, setDatasetPopoverOpen] = useState(false)

  // Step 3: Column mappings
  const [sourceFields, setSourceFields] = useState<SchemaField[]>([])
  const [targetFields, setTargetFields] = useState<SchemaField[]>([])
  const [columnMappings, setColumnMappings] = useState<ColumnMapping[]>([])

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset on open
  useEffect(() => {
    if (open) {
      setStep(1)
      setDirection("source")
      setSelectedDatasetId(null)
      setRelationType("ETL")
      setSelectedPipelineId("none")
      setDescription("")
      setColumnMappings([])
      setSearchQuery("")
      setError(null)
    }
  }, [open])

  // Load platforms and pipelines on open
  useEffect(() => {
    if (!open) return
    authFetch(`${BASE}/platforms`).then(r => r.json()).then(setPlatforms).catch(() => {})
    authFetch(`${BASE}/pipelines`).then(r => r.json()).then(setPipelines).catch(() => {})
  }, [open])

  // Search datasets when platform or query changes
  useEffect(() => {
    if (!open || step < 2) return
    const params = new URLSearchParams()
    if (searchQuery) params.set("search", searchQuery)
    if (selectedPlatformId && selectedPlatformId !== "all") {
      params.set("platform", selectedPlatformId)
    }
    params.set("page_size", "50")

    authFetch(`${BASE}/datasets?${params}`)
      .then(r => r.json())
      .then(data => {
        // Filter out current dataset
        const items = (data.items || []).filter(
          (d: DatasetSummary) => d.id !== datasetId
        )
        setDatasets(items)
      })
      .catch(() => {})
  }, [open, step, searchQuery, selectedPlatformId, datasetId])

  // Load schema fields when entering step 3
  const loadSchemaFields = useCallback(async () => {
    if (!selectedDatasetId) return

    const sourceId = direction === "source" ? datasetId : selectedDatasetId
    const targetId = direction === "source" ? selectedDatasetId : datasetId

    try {
      const [srcResp, tgtResp] = await Promise.all([
        authFetch(`${BASE}/datasets/${sourceId}`),
        authFetch(`${BASE}/datasets/${targetId}`),
      ])
      const srcData = await srcResp.json()
      const tgtData = await tgtResp.json()
      setSourceFields(srcData.schema_fields || [])
      setTargetFields(tgtData.schema_fields || [])
    } catch {
      setSourceFields([])
      setTargetFields([])
    }
  }, [datasetId, selectedDatasetId, direction])

  const selectedDataset = datasets.find(d => d.id === selectedDatasetId)

  // Step navigation
  const goToStep2 = () => setStep(2)
  const goToStep3 = () => {
    loadSchemaFields()
    setStep(3)
  }

  // Column mapping helpers
  const addMappingRow = () => {
    setColumnMappings(prev => [
      ...prev,
      { source_column: "", target_column: "", transform_type: "DIRECT", transform_expr: "" },
    ])
  }

  const updateMapping = (index: number, field: keyof ColumnMapping, value: string) => {
    setColumnMappings(prev =>
      prev.map((m, i) => (i === index ? { ...m, [field]: value } : m))
    )
  }

  const removeMapping = (index: number) => {
    setColumnMappings(prev => prev.filter((_, i) => i !== index))
  }

  // Save
  const handleSave = async () => {
    if (!selectedDatasetId) return
    setSaving(true)
    setError(null)

    const sourceId = direction === "source" ? datasetId : selectedDatasetId
    const targetId = direction === "source" ? selectedDatasetId : datasetId

    const validMappings = columnMappings.filter(
      m => m.source_column && m.target_column
    )

    const body = {
      source_dataset_id: sourceId,
      target_dataset_id: targetId,
      relation_type: relationType,
      lineage_source: selectedPipelineId !== "none" ? "PIPELINE" : "MANUAL",
      pipeline_id: selectedPipelineId !== "none" ? Number(selectedPipelineId) : null,
      description: description || null,
      column_mappings: validMappings,
    }

    try {
      const resp = await authFetch(`${BASE}/lineage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${resp.status}`)
      }
      onCreated()
      onOpenChange(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Lineage Relationship</DialogTitle>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex items-center gap-2 text-sm mb-2">
          <StepIndicator n={1} label="Direction" current={step} />
          <div className="h-px flex-1 bg-border" />
          <StepIndicator n={2} label="Dataset" current={step} />
          <div className="h-px flex-1 bg-border" />
          <StepIndicator n={3} label="Columns" current={step} />
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded px-3 py-2">
            {error}
          </p>
        )}

        {/* ============ Step 1: Direction ============ */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="rounded-lg border px-4 py-3 bg-muted/30">
              <p className="text-sm font-medium">{datasetName}</p>
              <p className="text-sm text-muted-foreground">Current dataset</p>
            </div>

            <Label className="text-sm font-medium">This dataset is:</Label>

            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setDirection("source")}
                className={`rounded-lg border-2 p-4 text-left transition-colors ${
                  direction === "source"
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-muted-foreground/50"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <ArrowDown className="h-5 w-5 text-blue-500" />
                  <span className="font-medium text-sm">Source (Upstream)</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  This dataset provides data to another dataset
                </p>
              </button>

              <button
                type="button"
                onClick={() => setDirection("target")}
                className={`rounded-lg border-2 p-4 text-left transition-colors ${
                  direction === "target"
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-muted-foreground/50"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <ArrowUp className="h-5 w-5 text-green-500" />
                  <span className="font-medium text-sm">Target (Downstream)</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  This dataset receives data from another dataset
                </p>
              </button>
            </div>

            <div className="flex justify-end">
              <Button onClick={goToStep2}>Next</Button>
            </div>
          </div>
        )}

        {/* ============ Step 2: Dataset Selection ============ */}
        {step === 2 && (
          <div className="space-y-4">
            {/* Direction summary */}
            <div className="flex items-center gap-2 text-sm rounded-lg border px-4 py-3 bg-muted/30">
              {direction === "source" ? (
                <>
                  <span className="font-medium">{datasetName}</span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  <span className="text-muted-foreground">?</span>
                </>
              ) : (
                <>
                  <span className="text-muted-foreground">?</span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{datasetName}</span>
                </>
              )}
            </div>

            {/* Platform filter */}
            <div className="space-y-1.5">
              <Label className="text-sm">Platform</Label>
              <Select value={selectedPlatformId} onValueChange={setSelectedPlatformId}>
                <SelectTrigger className="h-9">
                  <SelectValue placeholder="All Platforms" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Platforms</SelectItem>
                  {platforms.map(p => (
                    <SelectItem key={p.id} value={p.platform_id}>
                      {p.name} ({p.type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Dataset search */}
            <div className="space-y-1.5">
              <Label className="text-sm">
                {direction === "source" ? "Target Dataset" : "Source Dataset"}
              </Label>
              <Popover open={datasetPopoverOpen} onOpenChange={setDatasetPopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    className="w-full justify-between h-9 font-normal"
                  >
                    {selectedDataset
                      ? `${selectedDataset.platform_type} > ${selectedDataset.name}`
                      : "Search and select dataset..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[560px] p-0" align="start">
                  <Command shouldFilter={false}>
                    <CommandInput
                      placeholder="Search datasets..."
                      value={searchQuery}
                      onValueChange={setSearchQuery}
                    />
                    <CommandList>
                      <CommandEmpty>No datasets found.</CommandEmpty>
                      <CommandGroup>
                        {datasets.map(d => (
                          <CommandItem
                            key={d.id}
                            value={String(d.id)}
                            onSelect={() => {
                              setSelectedDatasetId(d.id)
                              setDatasetPopoverOpen(false)
                            }}
                          >
                            <Check
                              className={`mr-2 h-4 w-4 ${
                                selectedDatasetId === d.id ? "opacity-100" : "opacity-0"
                              }`}
                            />
                            <Badge variant="outline" className="mr-2 text-sm px-1.5 py-0">
                              {d.platform_type}
                            </Badge>
                            <span className="truncate">{d.name}</span>
                            <span className="ml-auto text-sm text-muted-foreground truncate">
                              {d.platform_name}
                            </span>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Relation type */}
            <div className="space-y-1.5">
              <Label className="text-sm">Relation Type</Label>
              <Select value={relationType} onValueChange={setRelationType}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ETL">ETL</SelectItem>
                  <SelectItem value="FILE_EXPORT">File Export</SelectItem>
                  <SelectItem value="CDC">CDC</SelectItem>
                  <SelectItem value="REPLICATION">Replication</SelectItem>
                  <SelectItem value="DERIVED">Derived</SelectItem>
                  <SelectItem value="READ_WRITE">Read/Write</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Pipeline (optional) */}
            <div className="space-y-1.5">
              <Label className="text-sm">Pipeline (optional)</Label>
              <Select value={selectedPipelineId} onValueChange={setSelectedPipelineId}>
                <SelectTrigger className="h-9">
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {pipelines.map(p => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.pipeline_name} ({p.pipeline_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label className="text-sm">Description (optional)</Label>
              <Textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="e.g., HR data exported as Parquet and loaded into Impala"
                rows={2}
                className="text-sm"
              />
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
              <Button onClick={goToStep3} disabled={!selectedDatasetId}>
                Next
              </Button>
            </div>
          </div>
        )}

        {/* ============ Step 3: Column Mapping ============ */}
        {step === 3 && (
          <div className="space-y-4">
            {/* Summary */}
            <div className="flex items-center gap-2 text-sm rounded-lg border px-4 py-3 bg-muted/30">
              <span className="font-medium">
                {direction === "source" ? datasetName : selectedDataset?.name}
              </span>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">
                {direction === "source" ? selectedDataset?.name : datasetName}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">
                Column Mapping
                <span className="text-sm text-muted-foreground font-normal ml-2">
                  (optional - for impact analysis)
                </span>
              </Label>
              <Button variant="outline" size="sm" onClick={addMappingRow}>
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Row
              </Button>
            </div>

            {columnMappings.length > 0 && (
              <div className="space-y-2">
                {/* Header */}
                <div className="grid grid-cols-[1fr_auto_1fr_100px_32px] gap-2 items-center text-sm text-muted-foreground px-1">
                  <span>Source Column</span>
                  <span />
                  <span>Target Column</span>
                  <span>Type</span>
                  <span />
                </div>

                {columnMappings.map((m, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-[1fr_auto_1fr_100px_32px] gap-2 items-center"
                  >
                    {/* Source column */}
                    <Select
                      value={m.source_column}
                      onValueChange={v => updateMapping(i, "source_column", v)}
                    >
                      <SelectTrigger className="h-9 text-sm">
                        <SelectValue placeholder="Select..." />
                      </SelectTrigger>
                      <SelectContent>
                        {sourceFields.map(f => (
                          <SelectItem key={f.field_path} value={f.field_path}>
                            {f.field_path}
                            <span className="text-muted-foreground ml-1">({f.field_type})</span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />

                    {/* Target column */}
                    <Select
                      value={m.target_column}
                      onValueChange={v => updateMapping(i, "target_column", v)}
                    >
                      <SelectTrigger className="h-9 text-sm">
                        <SelectValue placeholder="Select..." />
                      </SelectTrigger>
                      <SelectContent>
                        {targetFields.map(f => (
                          <SelectItem key={f.field_path} value={f.field_path}>
                            {f.field_path}
                            <span className="text-muted-foreground ml-1">({f.field_type})</span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {/* Transform type */}
                    <Select
                      value={m.transform_type}
                      onValueChange={v => updateMapping(i, "transform_type", v)}
                    >
                      <SelectTrigger className="h-9 text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="DIRECT">Direct</SelectItem>
                        <SelectItem value="CAST">Cast</SelectItem>
                        <SelectItem value="EXPRESSION">Expr</SelectItem>
                        <SelectItem value="DERIVED">Derived</SelectItem>
                      </SelectContent>
                    </Select>

                    {/* Delete */}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => removeMapping(i)}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            {columnMappings.length === 0 && (
              <div className="text-center py-6 text-sm text-muted-foreground border rounded-lg border-dashed">
                No column mappings added.
                <br />
                <span className="text-sm">
                  You can skip this step and add mappings later.
                </span>
              </div>
            )}

            <Separator />

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleSave}
                  disabled={saving}
                >
                  Skip & Save
                </Button>
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? "Saving..." : "Save"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Step indicator
// ---------------------------------------------------------------------------

function StepIndicator({
  n,
  label,
  current,
}: {
  n: number
  label: string
  current: number
}) {
  const done = current > n
  const active = current === n

  return (
    <div className="flex items-center gap-1.5">
      <div
        className={`w-5 h-5 rounded-full flex items-center justify-center text-sm font-medium ${
          done
            ? "bg-primary text-primary-foreground"
            : active
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground"
        }`}
      >
        {done ? <Check className="h-3 w-3" /> : n}
      </div>
      <span
        className={`${
          active ? "text-foreground font-medium" : "text-muted-foreground"
        }`}
      >
        {label}
      </span>
    </div>
  )
}
