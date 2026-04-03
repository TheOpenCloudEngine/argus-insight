"use client"

import { useCallback, useRef, useState } from "react"
import {
  ReactFlow,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  type Connection,
  type Node,
  type Edge,
  type NodeTypes,
  Handle,
  Position,
  MarkerType,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"

import {
  Code,
  Database,
  Eye,
  Filter,
  FlaskConical,
  FolderOpen,
  Loader2,
  Play,
  Save,
  Settings2,
  Sparkles,
  Upload,
  X,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

// ── Node types catalog ────────────────────────────────────

const NODE_CATALOG = [
  {
    category: "Source",
    icon: Database,
    color: "#3b82f6",
    nodes: [
      { type: "source_csv", label: "CSV / TSV File", tooltip: "Load CSV or TSV file from MinIO storage", defaults: { path: "", bucket: "", delimiter: "auto", encoding: "utf-8", has_header: true, columns: [] } },
      { type: "source_parquet", label: "Parquet File", tooltip: "Load Apache Parquet columnar data from MinIO", defaults: { path: "", bucket: "", columns: [] } },
      { type: "source_database", label: "Database Query", tooltip: "Load data from PostgreSQL, MariaDB, or Trino via SQL query", defaults: { db_type: "postgresql", connection: "", mode: "sql", schema: "", table: "", query: "", username: "", password: "", columns: [] } },
    ],
  },
  {
    category: "Transform",
    icon: Filter,
    color: "#f59e0b",
    nodes: [
      { type: "transform_fillnull", label: "Fill Null", tooltip: "Handle missing values using mean, median, mode, constant, or drop rows", defaults: { strategy: "median", constant_value: "0", apply_to: "all" } },
      { type: "transform_drop_cols", label: "Drop Columns", tooltip: "Remove unwanted columns (ID, name, etc.) that should not be used for training", defaults: { columns: "" } },
      { type: "transform_drop_dup", label: "Drop Duplicates", tooltip: "Remove duplicate rows to prevent bias in training", defaults: { subset: "", keep: "first" } },
      { type: "transform_typecast", label: "Type Cast", tooltip: "Change column data types (e.g., string→integer, integer→category)", defaults: { casts: [{ column: "", to_type: "int" }] } },
      { type: "transform_outlier", label: "Outlier Remove", tooltip: "Detect and remove outliers using IQR or Z-score method", defaults: { method: "iqr", threshold: 1.5, columns: "" } },
      { type: "transform_datetime", label: "Datetime Extract", tooltip: "Extract year, month, day, dayofweek, hour from datetime columns", defaults: { column: "", extract: ["year", "month", "day", "dayofweek"] } },
      { type: "transform_binning", label: "Binning", tooltip: "Convert continuous values to discrete bins (e.g., age → 10s, 20s, 30s)", defaults: { column: "", bins: 5, strategy: "uniform", labels: "" } },
      { type: "transform_sample", label: "Sample", tooltip: "Take a random sample of rows for faster experimentation on large datasets", defaults: { n_rows: 10000, random_seed: 42 } },
      { type: "transform_sort", label: "Sort", tooltip: "Sort rows by column values (essential for time-series data)", defaults: { column: "", ascending: true } },
      { type: "transform_encode", label: "Encode", tooltip: "Convert categorical columns to numbers using Label, One-Hot, or Ordinal encoding", defaults: { method: "label", drop_first: false, ordinal_order: "", apply_to: "all" } },
      { type: "transform_scale", label: "Scale", tooltip: "Normalize numeric features using Standard, MinMax, or Robust scaling", defaults: { method: "standard", range_min: 0, range_max: 1, apply_to: "all" } },
      { type: "transform_filter", label: "Filter Rows", tooltip: "Remove rows based on conditions", defaults: { conditions: [{ column: "", operator: ">", value: "" }], logic: "AND" } },
      { type: "transform_feature", label: "Feature Engineering", tooltip: "Create new features from existing columns using expressions", defaults: { features: [{ name: "", expression: "" }] } },
      { type: "transform_split", label: "Train/Test Split", tooltip: "Split data into training and test sets with configurable ratio and stratification", defaults: { test_size: 0.2, target_column: "", stratify: true, random_seed: 42 } },
    ],
  },
  {
    category: "Model",
    icon: FlaskConical,
    color: "#22c55e",
    nodes: [
      { type: "model_xgboost", label: "XGBoost", tooltip: "Gradient boosted trees — high accuracy, handles missing values, fast training", defaults: { n_estimators: 100, max_depth: 6, learning_rate: 0.1 } },
      { type: "model_lightgbm", label: "LightGBM", tooltip: "Light gradient boosting — faster than XGBoost for large datasets, lower memory", defaults: { n_estimators: 100, max_depth: -1, learning_rate: 0.1 } },
      { type: "model_rf", label: "Random Forest", tooltip: "Ensemble of decision trees — robust, less overfitting, good baseline model", defaults: { n_estimators: 100, max_depth: null } },
      { type: "model_linear", label: "Linear / Logistic", tooltip: "Simple linear model — fast, interpretable, good for linearly separable data", defaults: { max_iter: 500 } },
      { type: "model_automl", label: "AutoML", tooltip: "Automatically try multiple algorithms and select the best model within time limit", defaults: { time_limit: 300, metric: "auto" } },
    ],
  },
  {
    category: "Output",
    icon: Upload,
    color: "#8b5cf6",
    nodes: [
      { type: "output_mlflow", label: "MLflow Log", tooltip: "Log model, metrics, and parameters to MLflow experiment tracking", defaults: { experiment_name: "default" } },
      { type: "output_evaluate", label: "Evaluate", tooltip: "Calculate performance metrics (F1, accuracy, AUC, RMSE) and feature importance", defaults: { metrics: ["f1", "accuracy", "auc"] } },
      { type: "output_kserve", label: "KServe Deploy", tooltip: "Deploy the trained model as a REST API endpoint via KServe", defaults: { cpu: "1", memory: "2Gi" } },
      { type: "output_csv", label: "CSV Export", tooltip: "Export predictions or processed data to CSV file in MinIO", defaults: { bucket: "", path: "", filename: "" } },
    ],
  },
]

// ── Connection rules ──────────────────────────────────────

function getNodeCategory(nodeType: string): string {
  if (nodeType.startsWith("source_")) return "source"
  if (nodeType.startsWith("transform_")) return "transform"
  if (nodeType.startsWith("model_")) return "model"
  if (nodeType.startsWith("output_")) return "output"
  return ""
}

const ALLOWED_CONNECTIONS: Record<string, string[]> = {
  source: ["transform"],
  transform: ["transform", "model"],
  transform_split: ["model"],  // Split → Model only (no more transforms after split)
  model: ["output"],
  output: [],  // Output cannot connect to anything
}

// ── Custom Node Component ─────────────────────────────────

function getNodeSummary(nodeType: string, config: Record<string, any>): { text: string; warning?: string } {
  const c = config
  switch (nodeType) {
    // Source
    case "source_csv": {
      if (!c.path) return { text: "", warning: "Select file" }
      const file = c.path.split("/").pop() || c.path
      const colCount = (c.columns || []).length
      return { text: colCount > 0 ? `${file} (${colCount} cols)` : file }
    }
    case "source_parquet": {
      if (!c.path) return { text: "", warning: "Select file" }
      const colCount = (c.columns || []).length
      const name = c.path.split("/").pop() || c.path
      return { text: colCount > 0 ? `${name} (${colCount} cols)` : name }
    }
    case "source_database": {
      if (c.mode === "table" && c.table) return { text: `${c.schema || ""}.${c.table}` }
      if (c.mode === "sql" && c.query) return { text: c.query.slice(0, 25) + (c.query.length > 25 ? "..." : "") }
      return { text: "", warning: "Configure query" }
    }
    // Transform
    case "transform_fillnull":
      return { text: `${c.strategy || "median"} · ${c.apply_to || "all"}` }
    case "transform_drop_cols": {
      if (!c.columns) return { text: "", warning: "Select columns" }
      const cols = c.columns.split(",").map((s: string) => s.trim()).filter(Boolean)
      return { text: cols.length <= 3 ? cols.join(", ") : `${cols.length} columns` }
    }
    case "transform_drop_dup":
      return { text: `keep: ${c.keep || "first"}` }
    case "transform_typecast": {
      const casts = c.casts || []
      if (casts.length === 0) return { text: "", warning: "Add casts" }
      return { text: `${casts.length} cast${casts.length > 1 ? "s" : ""}` }
    }
    case "transform_outlier":
      return { text: `${(c.method || "iqr").toUpperCase()} × ${c.threshold ?? 1.5}` }
    case "transform_datetime": {
      if (!c.column) return { text: "", warning: "Select column" }
      const parts = c.extract || []
      return { text: `${c.column} → ${parts.length} parts` }
    }
    case "transform_binning": {
      if (!c.column) return { text: "", warning: "Select column" }
      return { text: `${c.column} → ${c.bins || 5} bins` }
    }
    case "transform_sample":
      return { text: `${(c.n_rows || 10000).toLocaleString()} rows` }
    case "transform_sort": {
      if (!c.column) return { text: "", warning: "Select column" }
      return { text: `${c.column} ${c.ascending !== false ? "↑" : "↓"}` }
    }
    case "transform_encode":
      return { text: `${c.method || "label"} · ${c.apply_to || "all"}` }
    case "transform_scale": {
      const m = c.method || "standard"
      const extra = m === "minmax" ? ` [${c.range_min ?? 0}~${c.range_max ?? 1}]` : ""
      return { text: `${m}${extra}` }
    }
    case "transform_filter": {
      const conds = c.conditions || []
      if (conds.length === 0 || !conds[0]?.column) return { text: "", warning: "Add conditions" }
      return { text: `${conds.length} condition${conds.length > 1 ? "s" : ""} (${c.logic || "AND"})` }
    }
    case "transform_feature": {
      const feats = c.features || []
      if (feats.length === 0 || !feats[0]?.name) return { text: "", warning: "Add features" }
      return { text: `${feats.length} new feature${feats.length > 1 ? "s" : ""}` }
    }
    case "transform_split": {
      if (!c.target_column) return { text: "", warning: "Set target column" }
      const train = Math.round((1 - (c.test_size || 0.2)) * 100)
      const test = Math.round((c.test_size || 0.2) * 100)
      return { text: `${train}/${test} · ${c.target_column}` }
    }
    // Model
    case "model_xgboost":
      return { text: `n=${c.n_estimators || 100} d=${c.max_depth || 6} lr=${c.learning_rate || 0.1}` }
    case "model_lightgbm":
      return { text: `n=${c.n_estimators || 100} d=${c.max_depth ?? -1} lr=${c.learning_rate || 0.1}` }
    case "model_rf":
      return { text: `n=${c.n_estimators || 100}` }
    case "model_linear":
      return { text: `iter=${c.max_iter || 500}` }
    case "model_automl": {
      const mins = Math.floor((c.time_limit || 300) / 60)
      return { text: `${mins}min · ${c.metric || "auto"}` }
    }
    // Output
    case "output_mlflow": {
      if (!c.experiment_name) return { text: "", warning: "Set experiment" }
      return { text: `exp: ${c.experiment_name}` }
    }
    case "output_evaluate": {
      const m = Array.isArray(c.metrics) ? c.metrics : []
      return { text: `${m.length} metric${m.length !== 1 ? "s" : ""}` }
    }
    case "output_kserve":
      return { text: `${c.cpu || "1"} cpu · ${c.memory || "2Gi"}` }
    case "output_csv": {
      if (!c.bucket && !c.path && !c.filename) return { text: "", warning: "Browse storage" }
      const fname = c.filename || ""
      return { text: fname || c.path || c.bucket }
    }
    default:
      return { text: "" }
  }
}

function PipelineNode({ data, selected }: { data: any; selected: boolean }) {
  const cat = NODE_CATALOG.find((c) =>
    c.nodes.some((n) => n.type === data.nodeType),
  )
  const color = cat?.color || "#6b7280"
  const Icon = cat?.icon || Settings2
  const category = getNodeCategory(data.nodeType)
  const hasInput = category !== "source"
  const hasOutput = category !== "output"
  const hasError = data._hasError
  const summary = getNodeSummary(data.nodeType, data.config || {})
  const isValid = !summary.warning && !hasError

  return (
    <div
      className={`rounded border bg-background shadow-sm transition-shadow ${
        selected ? "shadow-md ring-2 ring-primary" : ""
      } ${hasError ? "ring-2 ring-red-500 border-red-500" : ""}`}
      style={{ borderColor: hasError ? "#ef4444" : color }}
    >
      {hasInput && <Handle type="target" position={Position.Top} className="!bg-muted-foreground !w-2 !h-2" />}
      <div
        className="flex items-center gap-1.5 px-2 py-1 text-white text-sm font-medium"
        style={{ backgroundColor: color }}
      >
        <Icon className="h-3.5 w-3.5" />
        <span className="flex-1">{data.label}</span>
        {isValid && <span className="text-[10px]">✓</span>}
      </div>
      <div className="px-2 py-1 min-w-[100px]">
        {summary.warning ? (
          <div className="text-sm text-amber-500 italic">⚠ {summary.warning}</div>
        ) : summary.text ? (
          <div className="text-sm text-muted-foreground truncate max-w-[160px]" style={{ fontFamily: "'Roboto Condensed', Roboto, sans-serif" }}>{summary.text}</div>
        ) : null}
      </div>
      {hasOutput && <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground !w-2 !h-2" />}
    </div>
  )
}

const nodeTypes: NodeTypes = {
  pipeline: PipelineNode,
}

// ── Column propagation ───────────────────────────────────

import type { ColumnInfo } from "./column-select"

/**
 * Traverse graph backwards from a node to find the upstream Source node's columns.
 * Returns ColumnInfo[] (excluding columns marked as "exclude" in Source config).
 */
function getAvailableColumns(nodeId: string, nodes: Node[], edges: Edge[]): ColumnInfo[] {
  const visited = new Set<string>()
  const queue = [nodeId]

  while (queue.length > 0) {
    const current = queue.shift()!
    if (visited.has(current)) continue
    visited.add(current)

    const node = nodes.find((n) => n.id === current)
    if (!node) continue

    const nodeType = (node.data as any).nodeType as string

    // Found a Source node — return its columns
    if (nodeType.startsWith("source_")) {
      const cols: Array<{ name: string; dtype: string; action?: string }> =
        (node.data as any).config?.columns || []
      return cols
        .filter((c) => c.action !== "exclude")
        .map((c) => ({ name: c.name, dtype: c.dtype }))
    }

    // Walk upstream: find edges where this node is the target
    for (const edge of edges) {
      if (edge.target === current && !visited.has(edge.source)) {
        queue.push(edge.source)
      }
    }
  }

  return []
}

// ── Config Panel ──────────────────────────────────────────

import { NODE_DOCS, type Lang } from "./node-docs"
import { validateNode, validatePipeline, type PipelineError, type ValidationError } from "./node-validation"
import { SourceCsvConfig, SourceParquetConfig, SourceDatabaseConfig } from "./source-configs"
import {
  FillNullConfig, EncodeConfig, ScaleConfig, SplitConfig, FilterConfig, FeatureEngConfig,
  DropColumnsConfig, DropDuplicatesConfig, TypeCastConfig, OutlierRemoveConfig,
  DatetimeExtractConfig, BinningConfig, SampleConfig, SortConfig,
} from "./transform-configs"
import { Separator } from "@workspace/ui/components/separator"
import { OutputCsvConfig } from "./output-configs"
import { authFetch } from "@/features/auth/auth-fetch"
import { SavePipelineDialog, LoadPipelineDialog, CodePreviewDialog } from "./pipeline-dialogs"

function ConfigPanel({
  node,
  onUpdate,
  onClose,
  lang,
  onLangChange,
  availableColumns,
}: {
  node: Node
  onUpdate: (id: string, config: Record<string, any>) => void
  onClose: () => void
  lang: Lang
  onLangChange: (l: Lang) => void
  availableColumns: ColumnInfo[]
}) {
  const config = (node.data as any).config || {}
  const nodeType = (node.data as any).nodeType as string
  const doc = NODE_DOCS[nodeType]

  const handleChange = (key: string, value: any) => {
    // Get latest config from the node in the nodes array (avoids stale closure)
    onUpdate(node.id, { ...config, [key]: value })
  }

  // Batch update multiple keys at once (avoids stale state when calling onChange multiple times)
  const handleBatchChange = (updates: Record<string, any>) => {
    onUpdate(node.id, { ...config, ...updates })
  }

  return (
    <Card className="w-[364px] shrink-0 overflow-y-auto">
      <CardHeader className="py-2 flex flex-row items-center justify-between">
        <CardTitle className="text-sm">{(node.data as any).label}</CardTitle>
        <div className="flex items-center gap-1">
          <Select value={lang} onValueChange={(v) => onLangChange(v as Lang)}>
            <SelectTrigger className="h-6 w-[60px] text-[10px] px-1.5"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="en" className="text-sm">EN</SelectItem>
              <SelectItem value="ko" className="text-sm">KO</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-0 text-sm">
        {/* Description & Usage */}
        {doc && (
          <>
            <p className="text-sm text-muted-foreground">{doc.description[lang]}</p>
            <div>
              <p className="text-sm font-medium mb-1">{lang === "en" ? "When to use" : "사용 시점"}</p>
              <ul className="list-disc pl-4 text-sm text-muted-foreground space-y-0.5">
                {doc.whenToUse[lang].map((tip, i) => <li key={i}>{tip}</li>)}
              </ul>
            </div>
            <Separator />
          </>
        )}

        {/* Parameters */}
        <p className="text-sm font-medium">{lang === "en" ? "Parameters" : "파라미터"}</p>

        {/* Source-specific UIs */}
        {nodeType === "source_csv" ? (
          <SourceCsvConfig config={config} onChange={handleChange} onBatchChange={handleBatchChange} />
        ) : nodeType === "source_parquet" ? (
          <SourceParquetConfig config={config} onChange={handleChange} onBatchChange={handleBatchChange} />
        ) : nodeType === "source_database" ? (
          <SourceDatabaseConfig config={config} onChange={handleChange} />

        /* Transform-specific UIs */
        ) : nodeType === "transform_fillnull" ? (
          <FillNullConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_drop_cols" ? (
          <DropColumnsConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_drop_dup" ? (
          <DropDuplicatesConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_typecast" ? (
          <TypeCastConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_outlier" ? (
          <OutlierRemoveConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_datetime" ? (
          <DatetimeExtractConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_binning" ? (
          <BinningConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_sample" ? (
          <SampleConfig config={config} onChange={handleChange} />
        ) : nodeType === "transform_sort" ? (
          <SortConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_encode" ? (
          <EncodeConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_scale" ? (
          <ScaleConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_split" ? (
          <SplitConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_filter" ? (
          <FilterConfig config={config} onChange={handleChange} columns={availableColumns} />
        ) : nodeType === "transform_feature" ? (
          <FeatureEngConfig config={config} onChange={handleChange} columns={availableColumns} />

        /* Output-specific UIs */
        ) : nodeType === "output_csv" ? (
          <OutputCsvConfig config={config} onChange={handleChange} onBatchChange={handleBatchChange} />
        ) : (
          Object.entries(config).map(([key, value]) => (
            <div key={key} className="space-y-1">
              <Label className="text-sm capitalize">{key.replace(/_/g, " ")}</Label>
              {typeof value === "boolean" ? (
                <Select value={String(value)} onValueChange={(v) => handleChange(key, v === "true")}>
                  <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true" className="text-sm">True</SelectItem>
                    <SelectItem value="false" className="text-sm">False</SelectItem>
                  </SelectContent>
                </Select>
              ) : typeof value === "number" ? (
                <Input type="number" value={value} onChange={(e) => handleChange(key, parseFloat(e.target.value) || 0)} className="h-8 text-sm" />
              ) : key === "metric" ? (
                <Select value={String(value)} onValueChange={(v) => handleChange(key, v)}>
                  <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto" className="text-sm">Auto</SelectItem>
                    <SelectItem value="f1" className="text-sm">F1</SelectItem>
                    <SelectItem value="accuracy" className="text-sm">Accuracy</SelectItem>
                    <SelectItem value="rmse" className="text-sm">RMSE</SelectItem>
                    <SelectItem value="auc" className="text-sm">AUC</SelectItem>
                  </SelectContent>
                </Select>
              ) : Array.isArray(value) ? (
                <Input value={value.join(", ")} onChange={(e) => handleChange(key, e.target.value.split(",").map((s) => s.trim()))} className="h-8 text-sm" />
              ) : (
                <Input value={String(value ?? "")} onChange={(e) => handleChange(key, e.target.value)} className="h-8 text-sm" />
              )}
              {doc?.params[key] && (
                <p className="text-[11px] text-muted-foreground leading-tight">{doc.params[key][lang]}</p>
              )}
            </div>
          ))
        )}

        {/* Connection info */}
        {doc && (
          <>
            <Separator />
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">📥 {lang === "en" ? "Input" : "입력"}:</span>
                <span>{doc.input[lang]}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">📤 {lang === "en" ? "Output" : "출력"}:</span>
                <span>{doc.output[lang]}</span>
              </div>
            </div>
          </>
        )}

        {/* Inline validation errors */}
        {(() => {
          const errs = validateNode(nodeType, config)
          if (errs.length === 0) return null
          return (
            <>
              <Separator />
              <div className="space-y-1">
                {errs.map((err, i) => (
                  <p key={i} className="text-sm text-red-500">⚠ {lang === "en" ? err.message : err.messageKo}</p>
                ))}
              </div>
            </>
          )
        })()}
      </CardContent>
    </Card>
  )
}

// ── Node Palette ──────────────────────────────────────────

function NodePalette({
  onDragStart,
}: {
  onDragStart: (event: React.DragEvent, nodeType: string, label: string, defaults: Record<string, any>) => void
}) {
  return (
    <div className="w-[180px] shrink-0 space-y-3 overflow-y-auto pr-2">
      {NODE_CATALOG.map((cat) => (
        <div key={cat.category}>
          <div className="flex items-center gap-1.5 mb-1.5">
            <cat.icon className="h-3.5 w-3.5" style={{ color: cat.color }} />
            <span className="text-sm font-semibold">{cat.category}</span>
          </div>
          <div className="space-y-1">
            {cat.nodes.map((n) => (
              <div
                key={n.type}
                draggable
                onDragStart={(e) => onDragStart(e, n.type, n.label, n.defaults)}
                className="cursor-grab rounded border px-2 py-1.5 text-sm hover:bg-muted/50 active:cursor-grabbing transition-colors"
                style={{ borderLeftWidth: 3, borderLeftColor: cat.color }}
                title={n.tooltip}
              >
                {n.label}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main Modeler ──────────────────────────────────────────

export function MLStudioModeler({ onExecuted }: { onExecuted?: () => void } = {}) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[])
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [docLang, setDocLang] = useState<Lang>("en")
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)
  const idCounter = useRef(0)

  // Pipeline save/load state
  const [pipelineId, setPipelineId] = useState<number | null>(null)
  const [pipelineName, setPipelineName] = useState("")
  const [pipelineDesc, setPipelineDesc] = useState("")
  const [saveOpen, setSaveOpen] = useState(false)
  const [loadOpen, setLoadOpen] = useState(false)

  // Code preview state
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewCode, setPreviewCode] = useState("")

  // Validation
  const [pipelineErrors, setPipelineErrors] = useState<PipelineError[]>([])
  const [errorNodeIds, setErrorNodeIds] = useState<Set<string>>(new Set())

  // ── Workspace ID ───────────────────────────────────────
  const getWorkspaceId = useCallback((): number => {
    const stored = sessionStorage.getItem("argus_last_workspace_id")
    return stored ? parseInt(stored, 10) : 0
  }, [])

  // ── Helpers: serialize / deserialize pipeline ──────────
  const serializePipeline = useCallback(() => {
    const viewport = reactFlowInstance?.getViewport() || { x: 0, y: 0, zoom: 1 }
    return {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: (n.data as any).nodeType,
        label: (n.data as any).label,
        config: (n.data as any).config,
        position: n.position,
      })),
      edges: edges.map((e) => ({ id: e.id, from: e.source, to: e.target })),
      viewport,
      idCounter: idCounter.current,
    }
  }, [nodes, edges, reactFlowInstance])

  const loadPipeline = useCallback(
    (pipelineJson: Record<string, any>) => {
      const pNodes = (pipelineJson.nodes || []).map((n: any) => ({
        id: n.id,
        type: "pipeline" as const,
        position: n.position || { x: 0, y: 0 },
        data: { nodeType: n.type, label: n.label, config: n.config || {} },
      }))
      const pEdges = (pipelineJson.edges || []).map((e: any) => ({
        id: e.id || `e-${e.from}-${e.to}`,
        source: e.from,
        target: e.to,
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
      }))
      setNodes(pNodes)
      setEdges(pEdges)
      idCounter.current = pipelineJson.idCounter || pNodes.length
      if (pipelineJson.viewport && reactFlowInstance) {
        reactFlowInstance.setViewport(pipelineJson.viewport)
      }
      setSelectedNode(null)
      setPipelineErrors([])
      setErrorNodeIds(new Set())
    },
    [setNodes, setEdges, reactFlowInstance],
  )

  // ── Connection validation ──────────────────────────────
  const isValidConnection = useCallback(
    (connection: Edge | Connection) => {
      const sourceNode = nodes.find((n) => n.id === connection.source)
      const targetNode = nodes.find((n) => n.id === connection.target)
      if (!sourceNode || !targetNode) return false

      const sourceType = (sourceNode.data as any).nodeType as string
      const targetType = (targetNode.data as any).nodeType as string
      const sourceCat = getNodeCategory(sourceType)
      const targetCat = getNodeCategory(targetType)

      if (connection.source === connection.target) return false
      if (edges.some((e) => e.source === connection.source && e.target === connection.target)) return false
      if (sourceType === "transform_split") return targetCat === "model"

      const allowed = ALLOWED_CONNECTIONS[sourceCat] || []
      return allowed.includes(targetCat)
    },
    [nodes, edges],
  )

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, animated: true, markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 } }, eds)),
    [setEdges],
  )

  // ── Drag & Drop ────────────────────────────────────────
  const onDragStart = useCallback(
    (event: React.DragEvent, nodeType: string, label: string, defaults: Record<string, any>) => {
      event.dataTransfer.setData("application/reactflow-type", nodeType)
      event.dataTransfer.setData("application/reactflow-label", label)
      event.dataTransfer.setData("application/reactflow-defaults", JSON.stringify(defaults))
      event.dataTransfer.effectAllowed = "move"
    },
    [],
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = "move"
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const nodeType = event.dataTransfer.getData("application/reactflow-type")
      const label = event.dataTransfer.getData("application/reactflow-label")
      const defaults = JSON.parse(event.dataTransfer.getData("application/reactflow-defaults") || "{}")

      if (!nodeType || !reactFlowInstance) return

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      idCounter.current += 1
      const newNode: Node = {
        id: `node_${idCounter.current}`,
        type: "pipeline",
        position,
        data: { nodeType, label, config: { ...defaults } },
      }
      setNodes((nds) => [...nds, newNode])
    },
    [reactFlowInstance, setNodes],
  )

  const onNodeDoubleClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  const handleConfigUpdate = useCallback(
    (nodeId: string, config: Record<string, any>) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, config } } : n,
        ),
      )
      setSelectedNode((prev) =>
        prev && prev.id === nodeId ? { ...prev, data: { ...prev.data, config } } : prev,
      )
    },
    [setNodes],
  )

  // ── Pipeline validation ────────────────────────────────
  const validateAndGetPipeline = useCallback(() => {
    const errs = validatePipeline(nodes, edges)
    setPipelineErrors(errs)
    const errIds = new Set(errs.filter((e) => e.nodeId).map((e) => e.nodeId!))
    setErrorNodeIds(errIds)

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, _hasError: errIds.has(n.id) },
      })),
    )

    if (errs.length > 0) return null

    return {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: (n.data as any).nodeType,
        label: (n.data as any).label,
        config: (n.data as any).config,
      })),
      edges: edges.map((e) => ({ from: e.source, to: e.target })),
    }
  }, [nodes, edges, setNodes])

  // ── Build pipeline JSON for server ──────────────────────
  const buildPipelinePayload = useCallback(() => {
    return {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: (n.data as any).nodeType,
        label: (n.data as any).label,
        config: (n.data as any).config,
      })),
      edges: edges.map((e) => ({ from: e.source, to: e.target })),
    }
  }, [nodes, edges])

  // ── Toolbar actions ────────────────────────────────────
  const handlePreview = useCallback(async () => {
    const pipeline = validateAndGetPipeline()
    if (!pipeline) return

    const wsId = getWorkspaceId()
    const res = await authFetch("/api/v1/ml-studio/pipelines/codegen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace_id: wsId, pipeline_json: buildPipelinePayload() }),
    })

    if (res.ok) {
      const data = await res.json()
      if (data.errors?.length > 0) {
        setPipelineErrors(data.errors.map((e: any) => ({
          nodeId: e.nodeId, message: e.message, messageKo: e.message,
        })))
        return
      }
      if (data.warnings?.length > 0) {
        console.warn("Pipeline warnings:", data.warnings)
      }
      setPreviewCode(data.code)
      setPreviewOpen(true)
    } else {
      const err = await res.json().catch(() => ({}))
      alert(`Code generation failed: ${err.detail || res.statusText}`)
    }
  }, [validateAndGetPipeline, getWorkspaceId, buildPipelinePayload])

  const [executing, setExecuting] = useState(false)

  const handleExecute = useCallback(async () => {
    const pipeline = validateAndGetPipeline()
    if (!pipeline) return

    const wsId = getWorkspaceId()
    if (!wsId) {
      alert("No workspace selected. Visit the Workspaces page first.")
      return
    }

    setExecuting(true)
    try {
      const res = await authFetch("/api/v1/ml-studio/pipelines/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: wsId,
          name: pipelineName || "Modeler Pipeline",
          pipeline_id: pipelineId,
          pipeline_json: buildPipelinePayload(),
        }),
      })

      if (res.ok) {
        setPipelineErrors([])
        setErrorNodeIds(new Set())
        onExecuted?.()
      } else {
        const err = await res.json().catch(() => ({}))
        // Show server validation errors
        if (err.detail?.errors) {
          setPipelineErrors(err.detail.errors.map((e: any) => ({
            nodeId: e.nodeId, message: e.message, messageKo: e.message,
          })))
        } else {
          alert(`Execute failed: ${err.detail?.message || err.detail || res.statusText}`)
        }
      }
    } finally {
      setExecuting(false)
    }
  }, [validateAndGetPipeline, getWorkspaceId, buildPipelinePayload, pipelineId, pipelineName, onExecuted])

  const handleSaved = useCallback((id: number, name: string) => {
    setPipelineId(id)
    setPipelineName(name)
  }, [])

  const handleLoaded = useCallback(
    (id: number, name: string, description: string, pipelineJson: Record<string, any>) => {
      setPipelineId(id)
      setPipelineName(name)
      setPipelineDesc(description)
      loadPipeline(pipelineJson)
    },
    [loadPipeline],
  )

  return (
    <div className="flex flex-1 gap-3" style={{ minHeight: 0 }}>
      {/* Left: Node palette */}
      <NodePalette onDragStart={onDragStart} />

      {/* Center: React Flow canvas */}
      <div className="flex-1 rounded-lg border overflow-hidden relative" ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          isValidConnection={isValidConnection}
          onInit={setReactFlowInstance}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onNodeDoubleClick={onNodeDoubleClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          defaultViewport={{ x: 0, y: 0, zoom: 1 }}
          deleteKeyCode={["Backspace", "Delete"]}
          proOptions={{ hideAttribution: true }}
        >
          <Controls position="bottom-left" />
          <MiniMap
            position="bottom-right"
            nodeStrokeWidth={3}
            style={{ width: 120, height: 80 }}
          />
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} />

          {/* Empty state */}
          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center text-muted-foreground">
                <Sparkles className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Drag nodes from the left palette</p>
                <p className="text-sm mt-1">Connect them to build your ML pipeline</p>
              </div>
            </div>
          )}
        </ReactFlow>

        {/* Toolbar */}
        <div className="absolute top-3 right-3 flex gap-1.5 z-10">
          <Button size="sm" variant="outline" className="h-8 text-sm bg-background/80 backdrop-blur-sm" onClick={() => setLoadOpen(true)}>
            <FolderOpen className="mr-1.5 h-3.5 w-3.5" /> Load
          </Button>
          <Button size="sm" variant="outline" className="h-8 text-sm bg-background/80 backdrop-blur-sm" onClick={() => setSaveOpen(true)} disabled={nodes.length === 0}>
            <Save className="mr-1.5 h-3.5 w-3.5" /> Save
          </Button>
          <div className="w-px bg-border mx-0.5" />
          <Button size="sm" variant="outline" className="h-8 text-sm bg-background/80 backdrop-blur-sm" onClick={handlePreview} disabled={nodes.length === 0}>
            <Eye className="mr-1.5 h-3.5 w-3.5" /> Preview
          </Button>
          <Button size="sm" className="h-8 text-sm" onClick={handleExecute} disabled={nodes.length === 0 || executing}>
            {executing ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />} Execute
          </Button>
        </div>

        {/* Pipeline name badge */}
        {pipelineName && (
          <div className="absolute top-3 left-3 z-10">
            <Badge variant="secondary" className="text-sm bg-background/80 backdrop-blur-sm">
              {pipelineName}
            </Badge>
          </div>
        )}

        {/* Pipeline validation errors */}
        {pipelineErrors.length > 0 && (
          <div className="absolute bottom-3 left-3 right-3 z-10 max-h-[150px] overflow-y-auto rounded-lg border border-red-300 bg-red-50 dark:bg-red-950/30 p-3 shadow-lg">
            <p className="text-sm font-medium text-red-700 dark:text-red-400 mb-1">
              {pipelineErrors.length} validation error{pipelineErrors.length > 1 ? "s" : ""}
            </p>
            <ul className="space-y-0.5">
              {pipelineErrors.map((err, i) => (
                <li key={i} className="text-sm text-red-600 dark:text-red-400">
                  • {docLang === "en" ? err.message : err.messageKo}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Right: Config panel */}
      {selectedNode && (
        <ConfigPanel
          node={selectedNode}
          onUpdate={handleConfigUpdate}
          onClose={() => setSelectedNode(null)}
          lang={docLang}
          onLangChange={setDocLang}
          availableColumns={getAvailableColumns(selectedNode.id, nodes, edges)}
        />
      )}

      {/* Dialogs */}
      <SavePipelineDialog
        open={saveOpen}
        onOpenChange={setSaveOpen}
        workspaceId={getWorkspaceId()}
        pipelineJson={serializePipeline()}
        existingId={pipelineId}
        existingName={pipelineName}
        existingDescription={pipelineDesc}
        onSaved={handleSaved}
      />
      <LoadPipelineDialog
        open={loadOpen}
        onOpenChange={setLoadOpen}
        workspaceId={getWorkspaceId()}
        onLoad={handleLoaded}
      />
      <CodePreviewDialog
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        code={previewCode}
      />
    </div>
  )
}
