"use client"

import { useEffect, useMemo, useRef, useState, useCallback } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type EdgeMouseHandler,
  Position,
  Handle,
  useNodesState,
  useEdgesState,
  MarkerType,
  BackgroundVariant,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Separator } from "@workspace/ui/components/separator"
import { Database, ArrowRight, X, Link2, Plus, Trash2, GitBranch } from "lucide-react"
import Link from "next/link"
import { authFetch } from "@/features/auth/auth-fetch"
import { LineageAddDialog } from "./lineage-add-dialog"

const BASE = "/api/v1/catalog"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LineageNode = {
  id: number
  name: string
  urn: string
  platformType: string
  platformName: string
  isCurrent: boolean
}

type LineageEdge = {
  source: number
  target: number
  sourceTable: string
  targetTable: string
  lineageSource?: string   // QUERY_AGGREGATED | MANUAL | PIPELINE
  lineageId?: number | null
  relationType?: string
  description?: string
}

type ColumnLineageItem = {
  sourceDatasetId: number
  targetDatasetId: number
  sourceColumn: string
  targetColumn: string
  transformType: string
}

type LineageData = {
  datasetId: number
  nodes: LineageNode[]
  edges: LineageEdge[]
  columnLineage: ColumnLineageItem[]
}

type SelectedEdgeInfo = {
  sourceId: number
  targetId: number
  sourceName: string
  targetName: string
  columns: ColumnLineageItem[]
  joinKeys: ColumnLineageItem[]
  lineageSource?: string
  lineageId?: number | null
  relationType?: string
  description?: string
}

// ---------------------------------------------------------------------------
// Platform color palette
// ---------------------------------------------------------------------------

const PLATFORM_COLORS: Record<string, {
  border: string; bg: string; ring: string; icon: string; badge: string
}> = {
  PostgreSQL:  { border: "border-sky-500",     bg: "bg-sky-50 dark:bg-sky-950",         ring: "ring-sky-200",     icon: "text-sky-600",     badge: "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-200" },
  MySQL:       { border: "border-orange-500",  bg: "bg-orange-50 dark:bg-orange-950",   ring: "ring-orange-200",  icon: "text-orange-600",  badge: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200" },
  MariaDB:     { border: "border-orange-500",  bg: "bg-orange-50 dark:bg-orange-950",   ring: "ring-orange-200",  icon: "text-orange-600",  badge: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200" },
  Hive:        { border: "border-yellow-500",  bg: "bg-yellow-50 dark:bg-yellow-950",   ring: "ring-yellow-200",  icon: "text-yellow-600",  badge: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200" },
  Impala:      { border: "border-indigo-500",  bg: "bg-indigo-50 dark:bg-indigo-950",   ring: "ring-indigo-200",  icon: "text-indigo-600",  badge: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200" },
  Trino:       { border: "border-pink-500",    bg: "bg-pink-50 dark:bg-pink-950",       ring: "ring-pink-200",    icon: "text-pink-600",    badge: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200" },
  StarRocks:   { border: "border-violet-500",  bg: "bg-violet-50 dark:bg-violet-950",   ring: "ring-violet-200",  icon: "text-violet-600",  badge: "bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-200" },
  Kafka:       { border: "border-stone-600",   bg: "bg-stone-50 dark:bg-stone-950",     ring: "ring-stone-200",   icon: "text-stone-600",   badge: "bg-stone-100 text-stone-800 dark:bg-stone-900 dark:text-stone-200" },
  S3:          { border: "border-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950", ring: "ring-emerald-200", icon: "text-emerald-600", badge: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200" },
  Greenplum:   { border: "border-green-500",   bg: "bg-green-50 dark:bg-green-950",     ring: "ring-green-200",   icon: "text-green-600",   badge: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" },
  Oracle:      { border: "border-red-500",     bg: "bg-red-50 dark:bg-red-950",         ring: "ring-red-200",     icon: "text-red-600",     badge: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" },
  Kudu:        { border: "border-teal-500",    bg: "bg-teal-50 dark:bg-teal-950",       ring: "ring-teal-200",    icon: "text-teal-600",    badge: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200" },
  Spark:       { border: "border-amber-500",   bg: "bg-amber-50 dark:bg-amber-950",     ring: "ring-amber-200",   icon: "text-amber-600",   badge: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200" },
}

const DEFAULT_PLATFORM_COLOR = {
  border: "border-gray-400", bg: "bg-gray-50 dark:bg-gray-950", ring: "ring-gray-200",
  icon: "text-gray-500", badge: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
}

function getPlatformColor(platformType: string) {
  return PLATFORM_COLORS[platformType] ?? DEFAULT_PLATFORM_COLOR
}

// ---------------------------------------------------------------------------
// Custom Node Component
// ---------------------------------------------------------------------------

function DatasetNode({ data }: { data: LineageNode }) {
  const pc = getPlatformColor(data.platformType)

  const borderColor = data.isCurrent
    ? `${pc.border} ring-2 ${pc.ring}`
    : pc.border

  const bgColor = data.isCurrent
    ? pc.bg
    : "bg-card"

  return (
    <div
      className={`px-4 py-3 rounded-lg border-2 shadow-sm min-w-[200px] ${borderColor} ${bgColor}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground !w-2 !h-2" />

      <div className="flex items-center gap-2 mb-1">
        <Database className={`h-4 w-4 flex-shrink-0 ${pc.icon}`} />
        <Link
          href={`/dashboard/datasets/${data.id}`}
          className="text-sm font-semibold text-foreground hover:underline truncate"
        >
          {data.name}
        </Link>
      </div>
      <div className="flex items-center gap-1.5">
        <Badge className={`text-[10px] px-1.5 py-0 font-normal border-0 ${pc.badge}`}>
          {data.platformType}
        </Badge>
        <span className="text-xs text-muted-foreground truncate">
          {data.platformName}
        </span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-muted-foreground !w-2 !h-2" />
    </div>
  )
}

const nodeTypes = { dataset: DatasetNode }

// ---------------------------------------------------------------------------
// Transform type badge color
// ---------------------------------------------------------------------------

function transformBadge(type: string) {
  switch (type) {
    case "DIRECT":
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal">{type}</Badge>
    case "AGGREGATION":
      return <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">{type}</Badge>
    case "JOIN_KEY":
      return <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">{type}</Badge>
    case "EXPRESSION":
      return <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">{type}</Badge>
    case "CAST":
      return <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">{type}</Badge>
    default:
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal">{type}</Badge>
  }
}

// ---------------------------------------------------------------------------
// Lineage source badge
// ---------------------------------------------------------------------------

function lineageSourceBadge(source: string | undefined) {
  switch (source) {
    case "MANUAL":
      return (
        <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
          Manual
        </Badge>
      )
    case "PIPELINE":
      return (
        <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">
          Pipeline
        </Badge>
      )
    case "QUERY_AGGREGATED":
      return (
        <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal">
          Auto
        </Badge>
      )
    default:
      return null
  }
}

// ---------------------------------------------------------------------------
// Draggable + Resizable Lineage Detail Panel
// ---------------------------------------------------------------------------

function EdgeDetailPanel({
  info,
  onClose,
  onDelete,
}: {
  info: SelectedEdgeInfo
  onClose: () => void
  onDelete?: (lineageId: number) => void
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  const [size, setSize] = useState({ w: 420, h: 480 })
  const dragRef = useRef({ active: false, sx: 0, sy: 0, ox: 0, oy: 0 })
  const resizeRef = useRef({ active: false, sx: 0, sy: 0, ow: 0, oh: 0 })

  // Calculate initial position (top-right of container)
  useEffect(() => {
    if (pos) return
    const container = panelRef.current?.parentElement
    if (container) {
      containerRef.current = container as HTMLDivElement
      const rect = container.getBoundingClientRect()
      setPos({ left: rect.width - size.w - 16, top: 16 })
    } else {
      setPos({ left: 400, top: 16 })
    }
  }, [pos, size.w])

  // --- Drag ---
  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    if (!pos) return
    dragRef.current = { active: true, sx: e.clientX, sy: e.clientY, ox: pos.left, oy: pos.top }
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current.active) return
      setPos({
        left: dragRef.current.ox + (ev.clientX - dragRef.current.sx),
        top: dragRef.current.oy + (ev.clientY - dragRef.current.sy),
      })
    }
    const onUp = () => {
      dragRef.current.active = false
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
    }
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
  }, [pos])

  // --- Resize ---
  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    resizeRef.current = { active: true, sx: e.clientX, sy: e.clientY, ow: size.w, oh: size.h }
    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current.active) return
      setSize({
        w: Math.max(320, resizeRef.current.ow + (ev.clientX - resizeRef.current.sx)),
        h: Math.max(200, resizeRef.current.oh + (ev.clientY - resizeRef.current.sy)),
      })
    }
    const onUp = () => {
      resizeRef.current.active = false
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
    }
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
  }, [size])

  const isManual = info.lineageSource === "MANUAL" || info.lineageSource === "PIPELINE"

  if (!pos) return null

  return (
    <div
      ref={panelRef}
      className="absolute z-10"
      style={{ left: pos.left, top: pos.top, width: size.w, height: size.h }}
    >
      <Card className="h-full flex flex-col shadow-lg border-2">
        {/* Draggable header */}
        <CardHeader
          className="pb-3 cursor-move select-none flex-shrink-0"
          onMouseDown={onDragStart}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CardTitle className="text-sm font-medium">Lineage Detail</CardTitle>
              {lineageSourceBadge(info.lineageSource)}
            </div>
            <div className="flex items-center gap-1">
              {isManual && info.lineageId && onDelete && (
                <button
                  onClick={() => onDelete(info.lineageId!)}
                  onMouseDown={e => e.stopPropagation()}
                  className="text-muted-foreground hover:text-destructive p-0.5"
                  title="Delete lineage"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
              <button
                onClick={onClose}
                onMouseDown={e => e.stopPropagation()}
                className="text-muted-foreground hover:text-foreground p-0.5"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
            <span className="font-medium text-foreground">{info.sourceName}</span>
            <ArrowRight className="h-3 w-3" />
            <span className="font-medium text-foreground">{info.targetName}</span>
          </div>
        </CardHeader>

        {/* Scrollable content */}
        <CardContent className="pt-0 space-y-4 overflow-auto flex-1 min-h-0">
          {/* Lineage metadata for manual/pipeline */}
          {isManual && (
            <div className="space-y-1.5 text-xs">
              {info.relationType && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Relation</span>
                  <span className="font-medium">{info.relationType}</span>
                </div>
              )}
              {info.description && (
                <div>
                  <span className="text-muted-foreground">Description</span>
                  <p className="mt-0.5 text-foreground">{info.description}</p>
                </div>
              )}
              <Separator />
            </div>
          )}

          {/* JOIN Keys */}
          {info.joinKeys.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Link2 className="h-3.5 w-3.5 text-purple-600" />
                <span className="text-xs font-medium">JOIN Columns ({info.joinKeys.length})</span>
              </div>
              <div className="space-y-1.5">
                {info.joinKeys.map((jk, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-xs bg-purple-50 dark:bg-purple-950 rounded px-2.5 py-1.5"
                  >
                    <code className="font-mono text-purple-700 dark:text-purple-300">
                      {jk.sourceColumn}
                    </code>
                    <span className="text-muted-foreground">=</span>
                    <code className="font-mono text-purple-700 dark:text-purple-300">
                      {jk.targetColumn}
                    </code>
                    {transformBadge("JOIN_KEY")}
                  </div>
                ))}
              </div>
            </div>
          )}

          {info.joinKeys.length > 0 && info.columns.length > 0 && <Separator />}

          {/* Column Mappings */}
          {info.columns.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium">Column Mappings ({info.columns.length})</span>
              </div>
              <div className="space-y-1">
                {info.columns.map((cl, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between gap-2 text-xs bg-muted/50 rounded px-2.5 py-1.5"
                  >
                    <div className="flex items-center gap-1.5 min-w-0">
                      <code className="font-mono truncate text-foreground">
                        {cl.sourceColumn}
                      </code>
                      <ArrowRight className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                      <code className="font-mono truncate text-foreground">
                        {cl.targetColumn}
                      </code>
                    </div>
                    {transformBadge(cl.transformType)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {info.joinKeys.length === 0 && info.columns.length === 0 && (
            <p className="text-xs text-muted-foreground">
              No column-level detail available for this edge.
            </p>
          )}
        </CardContent>

        {/* Resize handle */}
        <div
          className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
          onMouseDown={onResizeStart}
        >
          <svg
            width="16" height="16" viewBox="0 0 16 16"
            className="text-muted-foreground/40 hover:text-muted-foreground"
          >
            <path d="M14 14L8 14L14 8Z" fill="currentColor" />
            <path d="M14 14L11 14L14 11Z" fill="currentColor" opacity="0.5" />
          </svg>
        </div>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Layout Helper - simple layered layout
// ---------------------------------------------------------------------------

function layoutNodes(
  lineageNodes: LineageNode[],
  lineageEdges: LineageEdge[],
  currentId: number,
): Node[] {
  const downstream = new Map<number, Set<number>>()
  const upstream = new Map<number, Set<number>>()

  for (const e of lineageEdges) {
    if (!downstream.has(e.source)) downstream.set(e.source, new Set())
    downstream.get(e.source)!.add(e.target)
    if (!upstream.has(e.target)) upstream.set(e.target, new Set())
    upstream.get(e.target)!.add(e.source)
  }

  const layers = new Map<number, number>()
  layers.set(currentId, 0)

  const upQueue = [currentId]
  const upVisited = new Set([currentId])
  while (upQueue.length > 0) {
    const node = upQueue.shift()!
    const parents = upstream.get(node)
    if (parents) {
      for (const p of parents) {
        if (!upVisited.has(p)) {
          upVisited.add(p)
          layers.set(p, (layers.get(node) ?? 0) - 1)
          upQueue.push(p)
        }
      }
    }
  }

  const downQueue = [currentId]
  const downVisited = new Set([currentId])
  while (downQueue.length > 0) {
    const node = downQueue.shift()!
    const children = downstream.get(node)
    if (children) {
      for (const c of children) {
        if (!downVisited.has(c)) {
          downVisited.add(c)
          layers.set(c, (layers.get(node) ?? 0) + 1)
          downQueue.push(c)
        }
      }
    }
  }

  for (const n of lineageNodes) {
    if (!layers.has(n.id)) layers.set(n.id, 0)
  }

  const layerGroups = new Map<number, LineageNode[]>()
  for (const n of lineageNodes) {
    const layer = layers.get(n.id) ?? 0
    if (!layerGroups.has(layer)) layerGroups.set(layer, [])
    layerGroups.get(layer)!.push(n)
  }

  const X_GAP = 300
  const Y_GAP = 100
  const sortedLayers = [...layerGroups.keys()].sort((a, b) => a - b)
  const minLayer = sortedLayers[0] ?? 0

  const nodes: Node[] = []
  for (const layer of sortedLayers) {
    const group = layerGroups.get(layer)!
    const x = (layer - minLayer) * X_GAP
    const startY = -((group.length - 1) * Y_GAP) / 2

    for (let i = 0; i < group.length; i++) {
      const n = group[i]!
      nodes.push({
        id: String(n.id),
        type: "dataset",
        position: { x, y: startY + i * Y_GAP },
        data: { ...n },
      })
    }
  }

  return nodes
}

// ---------------------------------------------------------------------------
// Edge style helpers
// ---------------------------------------------------------------------------

/** Auto-collected edges are dashed; manual/pipeline edges are solid */
function edgeStyle(lineageSource: string | undefined, isSelected: boolean) {
  const isManual = lineageSource === "MANUAL" || lineageSource === "PIPELINE"
  const color = isSelected ? "#8b5cf6" : isManual ? "#10b981" : "#6b7280"
  return {
    stroke: color,
    strokeWidth: isSelected ? 3 : 2,
    strokeDasharray: isManual ? undefined : "6 3",
    cursor: "pointer" as const,
  }
}

// ---------------------------------------------------------------------------
// LineageTab Component
// ---------------------------------------------------------------------------

export function LineageTab({
  datasetId,
  datasetName,
}: {
  datasetId: number
  datasetName: string
}) {
  const [lineageData, setLineageData] = useState<LineageData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<SelectedEdgeInfo | null>(null)
  const [addDialogOpen, setAddDialogOpen] = useState(false)

  const loadLineage = useCallback(async () => {
    try {
      setLoading(true)
      const resp = await authFetch(`${BASE}/datasets/${datasetId}/lineage`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      setLineageData(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load lineage")
    } finally {
      setLoading(false)
    }
  }, [datasetId])

  useEffect(() => {
    loadLineage()
  }, [loadLineage])

  // Build edge metadata map for quick lookup
  const edgeMetaMap = useMemo(() => {
    const m = new Map<string, LineageEdge>()
    if (lineageData) {
      for (const e of lineageData.edges) {
        m.set(`${e.source}-${e.target}`, e)
      }
    }
    return m
  }, [lineageData])

  const nodeNameMap = useMemo(() => {
    const m = new Map<number, string>()
    if (lineageData) {
      for (const n of lineageData.nodes) m.set(n.id, n.name)
    }
    return m
  }, [lineageData])

  const onEdgeClick: EdgeMouseHandler = (event, edge) => {
    if (!lineageData) return
    const srcId = Number(edge.source)
    const tgtId = Number(edge.target)

    const meta = edgeMetaMap.get(`${srcId}-${tgtId}`)

    // Find column lineage entries for this edge
    const allCols = lineageData.columnLineage.filter(
      cl => cl.sourceDatasetId === srcId && cl.targetDatasetId === tgtId,
    )

    const joinKeys = allCols.filter(cl => cl.transformType === "JOIN_KEY")
    const columns = allCols.filter(cl => cl.transformType !== "JOIN_KEY")

    setSelectedEdge({
      sourceId: srcId,
      targetId: tgtId,
      sourceName: nodeNameMap.get(srcId) ?? String(srcId),
      targetName: nodeNameMap.get(tgtId) ?? String(tgtId),
      columns,
      joinKeys,
      lineageSource: meta?.lineageSource,
      lineageId: meta?.lineageId,
      relationType: meta?.relationType,
      description: meta?.description,
    })
  }

  const handleDeleteLineage = async (lineageId: number) => {
    try {
      const resp = await authFetch(`${BASE}/lineage/${lineageId}`, { method: "DELETE" })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      setSelectedEdge(null)
      loadLineage()
    } catch {
      // silently fail
    }
  }

  const { flowNodes, flowEdges } = useMemo(() => {
    if (!lineageData || lineageData.nodes.length === 0) {
      return { flowNodes: [], flowEdges: [] }
    }

    const nodes = layoutNodes(lineageData.nodes, lineageData.edges, datasetId)

    const seen = new Set<string>()
    const edges: Edge[] = []

    for (let i = 0; i < lineageData.edges.length; i++) {
      const e = lineageData.edges[i]!
      const key = `${e.source}-${e.target}`
      if (seen.has(key)) continue
      seen.add(key)

      const isManual = e.lineageSource === "MANUAL" || e.lineageSource === "PIPELINE"

      edges.push({
        id: `e-${e.source}-${e.target}-${i}`,
        source: String(e.source),
        target: String(e.target),
        animated: !isManual,
        style: edgeStyle(e.lineageSource, false),
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isManual ? "#10b981" : "#6b7280",
        },
        label: "",
        interactionWidth: 20,
        data: { lineageSource: e.lineageSource },
      })
    }

    return { flowNodes: nodes, flowEdges: edges }
  }, [lineageData, datasetId])

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges)

  // Highlight selected edge
  useEffect(() => {
    if (!flowEdges.length) return

    const updated = flowEdges.map(e => {
      const srcId = Number(e.source)
      const tgtId = Number(e.target)
      const isSelected = selectedEdge
        && srcId === selectedEdge.sourceId
        && tgtId === selectedEdge.targetId

      const ls = e.data?.lineageSource as string | undefined

      return {
        ...e,
        style: edgeStyle(ls, !!isSelected),
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isSelected
            ? "#8b5cf6"
            : (ls === "MANUAL" || ls === "PIPELINE") ? "#10b981" : "#6b7280",
        },
      }
    })
    setEdges(updated)
  }, [selectedEdge, flowEdges, setEdges])

  useEffect(() => {
    setNodes(flowNodes)
  }, [flowNodes, setNodes])

  // -- Add Lineage button (always visible) --
  const addButton = (
    <Button
      variant="outline"
      size="sm"
      onClick={() => setAddDialogOpen(true)}
      className="gap-1.5"
    >
      <Plus className="h-3.5 w-3.5" />
      Add Lineage
    </Button>
  )

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <p className="text-sm text-muted-foreground">Loading lineage...</p>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <p className="text-sm text-destructive">Error: {error}</p>
        </CardContent>
      </Card>
    )
  }

  if (!lineageData || lineageData.nodes.length <= 1) {
    return (
      <>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 gap-4">
            <GitBranch className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              No lineage data available for this dataset.
            </p>
            {addButton}
          </CardContent>
        </Card>
        <LineageAddDialog
          open={addDialogOpen}
          onOpenChange={setAddDialogOpen}
          datasetId={datasetId}
          datasetName={datasetName}
          onCreated={loadLineage}
        />
      </>
    )
  }

  return (
    <>
      <Card>
        <CardContent className="p-0">
          <div style={{ height: 600 }} className="relative">
            {/* Floating toolbar */}
            <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
              {addButton}
            </div>

            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onEdgeClick={onEdgeClick}
              onPaneClick={() => setSelectedEdge(null)}
              nodeTypes={nodeTypes}
              defaultViewport={{ x: 50, y: 150, zoom: 1 }}
              minZoom={0.3}
              maxZoom={2}
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>

            {selectedEdge && (
              <EdgeDetailPanel
                info={selectedEdge}
                onClose={() => setSelectedEdge(null)}
                onDelete={handleDeleteLineage}
              />
            )}
          </div>

          <div className="px-4 py-2 border-t text-xs text-muted-foreground flex items-center gap-4">
            <span>Click on an edge to see column mappings.</span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-5 border-t-2 border-gray-400" style={{ borderStyle: "dashed" }} />
              Auto (query-based)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-5 border-t-2 border-emerald-500" />
              Manual / Pipeline
            </span>
          </div>
        </CardContent>
      </Card>

      <LineageAddDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        datasetId={datasetId}
        datasetName={datasetName}
        onCreated={loadLineage}
      />
    </>
  )
}
