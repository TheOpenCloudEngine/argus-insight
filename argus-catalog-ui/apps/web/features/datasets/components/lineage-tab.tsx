"use client"

import { useEffect, useMemo, useState } from "react"
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
import { Separator } from "@workspace/ui/components/separator"
import { Database, ArrowRight, X, Link2 } from "lucide-react"
import Link from "next/link"

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
}

// ---------------------------------------------------------------------------
// Custom Node Component
// ---------------------------------------------------------------------------

function DatasetNode({ data }: { data: LineageNode }) {
  const borderColor = data.isCurrent
    ? "border-blue-500 ring-2 ring-blue-200"
    : "border-border"

  const bgColor = data.isCurrent
    ? "bg-blue-50 dark:bg-blue-950"
    : "bg-card"

  return (
    <div
      className={`px-4 py-3 rounded-lg border-2 shadow-sm min-w-[200px] ${borderColor} ${bgColor}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground !w-2 !h-2" />

      <div className="flex items-center gap-2 mb-1">
        <Database className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        <Link
          href={`/dashboard/datasets/${data.id}`}
          className="text-sm font-semibold text-foreground hover:underline truncate"
        >
          {data.name}
        </Link>
      </div>
      <div className="text-xs text-muted-foreground">
        {data.platformName}
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
    default:
      return <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal">{type}</Badge>
  }
}

// ---------------------------------------------------------------------------
// Edge Detail Panel
// ---------------------------------------------------------------------------

function EdgeDetailPanel({
  info,
  onClose,
}: {
  info: SelectedEdgeInfo
  onClose: () => void
}) {
  return (
    <Card className="absolute top-4 right-4 w-[400px] max-h-[560px] overflow-auto z-10 shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Edge Detail</CardTitle>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
          <span className="font-medium text-foreground">{info.sourceName}</span>
          <ArrowRight className="h-3 w-3" />
          <span className="font-medium text-foreground">{info.targetName}</span>
        </div>
      </CardHeader>

      <CardContent className="pt-0 space-y-4">
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
    </Card>
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

  useEffect(() => {
    async function load() {
      try {
        setLoading(true)
        const resp = await fetch(`${BASE}/datasets/${datasetId}/lineage`)
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
        const data = await resp.json()
        setLineageData(data)
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load lineage")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [datasetId])

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

    // Find column lineage entries for this edge
    const allCols = lineageData.columnLineage.filter(
      cl => cl.sourceDatasetId === srcId && cl.targetDatasetId === tgtId,
    )

    // Also look for JOIN_KEY entries where this source table joined with another
    // source table that feeds into the same target
    const joinKeys = allCols.filter(cl => cl.transformType === "JOIN_KEY")
    const columns = allCols.filter(cl => cl.transformType !== "JOIN_KEY")

    setSelectedEdge({
      sourceId: srcId,
      targetId: tgtId,
      sourceName: nodeNameMap.get(srcId) ?? String(srcId),
      targetName: nodeNameMap.get(tgtId) ?? String(tgtId),
      columns,
      joinKeys,
    })
  }

  const { flowNodes, flowEdges } = useMemo(() => {
    if (!lineageData || lineageData.nodes.length === 0) {
      return { flowNodes: [], flowEdges: [] }
    }

    const nodes = layoutNodes(lineageData.nodes, lineageData.edges, datasetId)

    const edges: Edge[] = lineageData.edges.map((e, i) => ({
      id: `e-${e.source}-${e.target}-${i}`,
      source: String(e.source),
      target: String(e.target),
      animated: true,
      style: { stroke: "#6b7280", strokeWidth: 2, cursor: "pointer" },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#6b7280" },
      label: "",
      interactionWidth: 20,
    }))

    const seen = new Set<string>()
    const uniqueEdges = edges.filter(e => {
      const key = `${e.source}-${e.target}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })

    return { flowNodes: nodes, flowEdges: uniqueEdges }
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

      return {
        ...e,
        style: {
          ...e.style,
          stroke: isSelected ? "#8b5cf6" : "#6b7280",
          strokeWidth: isSelected ? 3 : 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isSelected ? "#8b5cf6" : "#6b7280",
        },
      }
    })
    setEdges(updated)
  }, [selectedEdge, flowEdges, setEdges])

  useEffect(() => {
    setNodes(flowNodes)
  }, [flowNodes, setNodes])

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
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <p className="text-sm text-muted-foreground">
            No lineage data available for this dataset.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent className="p-0">
        <div style={{ height: 600 }} className="relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onEdgeClick={onEdgeClick}
            onPaneClick={() => setSelectedEdge(null)}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.3 }}
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
            />
          )}
        </div>

        {!selectedEdge && (
          <div className="px-4 py-2 border-t text-xs text-muted-foreground">
            Click on an edge (arrow) to see column mappings and JOIN conditions.
          </div>
        )}
      </CardContent>
    </Card>
  )
}
