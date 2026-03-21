"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  Position,
  Handle,
  useNodesState,
  useEdgesState,
  MarkerType,
  BackgroundVariant,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { Card, CardContent } from "@workspace/ui/components/card"
import { Database, ArrowRight } from "lucide-react"
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

type LineageData = {
  datasetId: number
  nodes: LineageNode[]
  edges: LineageEdge[]
  columnLineage: {
    sourceDatasetId: number
    targetDatasetId: number
    sourceColumn: string
    targetColumn: string
    transformType: string
  }[]
}

// ---------------------------------------------------------------------------
// Custom Node Component
// ---------------------------------------------------------------------------

function DatasetNode({ data }: { data: LineageNode & { columnInfo?: string[] } }) {
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

      {data.columnInfo && data.columnInfo.length > 0 && (
        <div className="mt-2 pt-2 border-t border-border space-y-0.5">
          {data.columnInfo.map((col, i) => (
            <div key={i} className="text-[11px] text-muted-foreground flex items-center gap-1">
              <ArrowRight className="h-3 w-3 flex-shrink-0" />
              <span className="truncate">{col}</span>
            </div>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Right} className="!bg-muted-foreground !w-2 !h-2" />
    </div>
  )
}

const nodeTypes = { dataset: DatasetNode }

// ---------------------------------------------------------------------------
// Layout Helper - simple layered layout
// ---------------------------------------------------------------------------

function layoutNodes(
  lineageNodes: LineageNode[],
  lineageEdges: LineageEdge[],
  currentId: number,
): Node[] {
  // Build adjacency
  const downstream = new Map<number, Set<number>>()
  const upstream = new Map<number, Set<number>>()

  for (const e of lineageEdges) {
    if (!downstream.has(e.source)) downstream.set(e.source, new Set())
    downstream.get(e.source)!.add(e.target)
    if (!upstream.has(e.target)) upstream.set(e.target, new Set())
    upstream.get(e.target)!.add(e.source)
  }

  // Assign layers via BFS from current node
  const layers = new Map<number, number>()
  layers.set(currentId, 0)

  // BFS upstream (negative layers)
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

  // BFS downstream (positive layers)
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

  // For nodes not reached, place at layer 0
  for (const n of lineageNodes) {
    if (!layers.has(n.id)) layers.set(n.id, 0)
  }

  // Group by layer
  const layerGroups = new Map<number, LineageNode[]>()
  for (const n of lineageNodes) {
    const layer = layers.get(n.id) ?? 0
    if (!layerGroups.has(layer)) layerGroups.set(layer, [])
    layerGroups.get(layer)!.push(n)
  }

  // Position nodes
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

  const { flowNodes, flowEdges } = useMemo(() => {
    if (!lineageData || lineageData.nodes.length === 0) {
      return { flowNodes: [], flowEdges: [] }
    }

    const nodes = layoutNodes(lineageData.nodes, lineageData.edges, datasetId)

    // Add column info to nodes
    if (lineageData.columnLineage.length > 0) {
      for (const node of nodes) {
        const nid = Number(node.id)
        const cols = lineageData.columnLineage
          .filter(cl => cl.sourceDatasetId === nid || cl.targetDatasetId === nid)
          .slice(0, 5)  // limit to 5 columns per node
        if (cols.length > 0) {
          const colStrs = cols.map(cl => {
            if (cl.sourceDatasetId === nid) {
              return `${cl.sourceColumn} [${cl.transformType}]`
            }
            return `${cl.targetColumn} [${cl.transformType}]`
          })
          // Deduplicate
          ;(node.data as Record<string, unknown>).columnInfo = [...new Set(colStrs)]
        }
      }
    }

    const edges: Edge[] = lineageData.edges.map((e, i) => ({
      id: `e-${e.source}-${e.target}-${i}`,
      source: String(e.source),
      target: String(e.target),
      animated: true,
      style: { stroke: "#6b7280", strokeWidth: 2 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#6b7280" },
      label: "",
    }))

    // Deduplicate edges by source-target pair
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

  useEffect(() => {
    setNodes(flowNodes)
    setEdges(flowEdges)
  }, [flowNodes, flowEdges, setNodes, setEdges])

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
        <div style={{ height: 600 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
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
        </div>
      </CardContent>
    </Card>
  )
}
