"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import dynamic from "next/dynamic"
import {
  ArrowLeft, BookOpen, Box, Clock, Code2, Download, Globe, Grid3X3, Import, List, Loader2,
  MessageSquare, Plus, Search, User, X,
} from "lucide-react"

import {
  ReactFlow, Controls,
  type Node, type Edge, Position, Handle,
  MarkerType, useNodesState, useEdgesState,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"

import { Badge } from "@workspace/ui/components/badge"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@workspace/ui/components/dialog"
import { Label } from "@workspace/ui/components/label"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@workspace/ui/components/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { DashboardHeader } from "@/components/dashboard-header"
import { CommentSection } from "@/components/comments"
import { useAuth } from "@/features/auth"

import { OciHubDashboard } from "@/features/oci-hub/oci-hub-dashboard"
import {
  fetchOciModels, fetchOciModel, fetchVersions, updateReadme, importFromHuggingFace,
  type OciModelSummary, type OciModelDetail, type OciModelVersion,
  type PaginatedOciModels,
} from "@/features/oci-hub/api"

const MonacoEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.default), {
  ssr: false,
  loading: () => <div className="flex items-center justify-center h-[200px]"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>,
})

function formatSize(bytes: number): string {
  if (!bytes) return "-"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return "today"
  if (days === 1) return "1d ago"
  if (days < 30) return `${days}d ago`
  return `${Math.floor(days / 30)}mo ago`
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    draft: "bg-zinc-400", review: "bg-amber-500", approved: "bg-blue-500",
    production: "bg-green-500", deprecated: "bg-zinc-600", archived: "bg-zinc-800",
  }
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold text-white ${colors[status] || "bg-zinc-400"}`}>
      {status.toUpperCase()}
    </span>
  )
}

function SourceBadge({ sourceType }: { sourceType: string | null }) {
  if (!sourceType) return null
  const config: Record<string, { label: string; color: string }> = {
    huggingface: { label: "HuggingFace", color: "text-blue-600 bg-blue-50 border-blue-200" },
    my: { label: "My Model", color: "text-orange-600 bg-orange-50 border-orange-200" },
    file: { label: "File Import", color: "text-green-600 bg-green-50 border-green-200" },
    local: { label: "Local", color: "text-green-600 bg-green-50 border-green-200" },
  }
  const c = config[sourceType] || { label: sourceType, color: "text-zinc-600 bg-zinc-50 border-zinc-200" }
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${c.color}`}>
      {c.label}
    </span>
  )
}

// ─── Model Card (card in grid) ───

function ModelCard({
  model, onClick,
}: { model: OciModelSummary; onClick: () => void }) {
  return (
    <Card className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={onClick}>
      <CardContent className="pt-2 pb-2">
        <div className="flex items-center gap-2 mb-1.5">
          <Box className="h-5 w-5 text-primary shrink-0" />
          <h3 className="font-semibold text-base truncate" title={model.display_name || model.name}>{model.display_name || model.name}</h3>
        </div>
        {model.description && (
          <p className="text-sm text-muted-foreground line-clamp-2 mb-2">{model.description}</p>
        )}
        <div className="flex flex-wrap gap-1 mb-3">
          <SourceBadge sourceType={model.source_type} />
          {model.task && <Badge variant="secondary" className="text-xs">{model.task}</Badge>}
          {model.framework && <Badge variant="secondary" className="text-xs">{model.framework}</Badge>}
          {model.language && <Badge variant="outline" className="text-xs">{model.language}</Badge>}
          {model.tags?.map((t) => (
            <Badge key={t.id} variant="outline" className="text-xs" style={{ borderColor: t.color, color: t.color }}>
              {t.name}
            </Badge>
          ))}
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><Download className="h-3 w-3" />{model.download_count}</span>
          <span>{formatSize(model.total_size)}</span>
          <span>v{model.version_count}</span>
          <span className="ml-auto">{timeAgo(model.updated_at)}</span>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Lineage Graph ───

type LineageEntry = {
  id: number
  source_type: string
  source_id: string
  source_name: string | null
  relation_type: string
  description: string | null
}

const SOURCE_TYPE_COLORS: Record<string, { bg: string; border: string; icon: string }> = {
  dataset: { bg: "bg-blue-50", border: "border-blue-300", icon: "📊" },
  model: { bg: "bg-purple-50", border: "border-purple-300", icon: "🤖" },
  external: { bg: "bg-green-50", border: "border-green-300", icon: "🌐" },
}

const RELATION_LABELS: Record<string, string> = {
  trained_on: "trained on",
  fine_tuned_from: "fine-tuned from",
  distilled_from: "distilled from",
  derived_from: "derived from",
  produces: "produces",
}

function LineageNode({ data }: { data: { label: string; sourceType: string; isCurrent: boolean; description?: string } }) {
  const colors = SOURCE_TYPE_COLORS[data.sourceType] || SOURCE_TYPE_COLORS.external
  return (
    <div className={`px-4 py-3 rounded-lg border-2 shadow-sm min-w-[160px] text-center ${
      data.isCurrent ? "border-primary bg-primary/5 ring-2 ring-primary/20" : `${colors.border} ${colors.bg}`
    }`}>
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground !w-2 !h-2" />
      <div className="text-xs text-muted-foreground mb-1">
        {data.isCurrent ? "🤖 current model" : `${colors.icon} ${data.sourceType}`}
      </div>
      <div className="font-medium text-sm">{data.label}</div>
      {data.description && <div className="text-xs text-muted-foreground mt-1">{data.description}</div>}
      <Handle type="source" position={Position.Right} className="!bg-muted-foreground !w-2 !h-2" />
    </div>
  )
}

const lineageNodeTypes = { lineageNode: LineageNode }

function buildLineageNodesEdges(modelName: string, lineage: LineageEntry[]) {
  const inputs = lineage.filter((l) => l.relation_type !== "produces")
  const outputs = lineage.filter((l) => l.relation_type === "produces")

  const initNodes: Node[] = []
  const initEdges: Edge[] = []

  const centerX = 400
  const centerY = Math.max(inputs.length, outputs.length, 1) * 50

  initNodes.push({
    id: "current",
    type: "lineageNode",
    position: { x: centerX, y: centerY },
    draggable: true,
    data: { label: modelName, sourceType: "model", isCurrent: true },
  })

  inputs.forEach((l, i) => {
    const nodeId = `input-${l.id}`
    const spacing = 110
    const startY = centerY - ((inputs.length - 1) * spacing) / 2
    initNodes.push({
      id: nodeId, type: "lineageNode", draggable: true,
      position: { x: 50, y: startY + i * spacing },
      data: { label: l.source_name || l.source_id, sourceType: l.source_type, isCurrent: false, description: l.description },
    })
    initEdges.push({
      id: `edge-${l.id}`, source: nodeId, target: "current",
      label: RELATION_LABELS[l.relation_type] || l.relation_type,
      type: "default", animated: true,
      style: { stroke: "#6366f1" }, labelStyle: { fontSize: 11, fill: "#6366f1" },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#6366f1" },
    })
  })

  outputs.forEach((l, i) => {
    const nodeId = `output-${l.id}`
    const spacing = 110
    const startY = centerY - ((outputs.length - 1) * spacing) / 2
    initNodes.push({
      id: nodeId, type: "lineageNode", draggable: true,
      position: { x: 750, y: startY + i * spacing },
      data: { label: l.source_name || l.source_id, sourceType: l.source_type, isCurrent: false, description: l.description },
    })
    initEdges.push({
      id: `edge-${l.id}`, source: "current", target: nodeId,
      label: RELATION_LABELS[l.relation_type] || l.relation_type,
      type: "default", animated: true,
      style: { stroke: "#10b981" }, labelStyle: { fontSize: 11, fill: "#10b981" },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981" },
    })
  })

  return { initNodes, initEdges }
}

function LineageGraph({ modelName, lineage }: { modelName: string; lineage: LineageEntry[] }) {
  const { initNodes, initEdges } = useMemo(
    () => buildLineageNodesEdges(modelName, lineage),
    [modelName, lineage],
  )
  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges)

  if (lineage.length === 0) {
    return <p className="text-sm text-muted-foreground text-center py-8">No lineage entries yet.</p>
  }

  return (
    <div className="border rounded-lg" style={{ height: "450px" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={lineageNodeTypes}
        defaultViewport={{ x: 50, y: 150, zoom: 1 }}
        proOptions={{ hideAttribution: true }}
      >
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}

// ─── Files Tab ───

type S3File = { key: string; name: string; size: number; last_modified: string }
type S3Folder = { key: string; name: string }

function FilesTab({ modelName, latestVersion }: { modelName: string; latestVersion: number }) {
  const [path, setPath] = useState(`/${modelName}/v${latestVersion}`)
  const [folders, setFolders] = useState<S3Folder[]>([])
  const [files, setFiles] = useState<S3File[]>([])
  const [loading, setLoading] = useState(true)
  const [currentPath, setCurrentPath] = useState("")

  const load = useCallback(async (p: string) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ path: p })
      const res = await fetch(`/api/v1/model-store/browse/list?${params}`)
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      setFolders(data.folders || [])
      setFiles(data.files || [])
      setCurrentPath(data.current_path || p)
      setPath(p)
    } catch (err) {
      console.error("Failed to load files:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(`/${modelName}/v${latestVersion}`)
  }, [load, modelName, latestVersion])

  const handleDownload = useCallback(async (filePath: string) => {
    try {
      const params = new URLSearchParams({ path: filePath })
      const res = await fetch(`/api/v1/model-store/browse/download?${params}`)
      if (!res.ok) return
      const data = await res.json()
      window.open(data.url, "_blank")
    } catch (err) {
      console.error("Download error:", err)
    }
  }, [])

  // Breadcrumb segments
  const segments = currentPath.split("/").filter(Boolean)
  const basePath = `/${modelName}/v${latestVersion}`

  const totalSize = files.reduce((acc, f) => acc + f.size, 0)

  if (loading) return <p className="text-sm text-muted-foreground text-center py-8">Loading files...</p>

  return (
    <div className="space-y-3">
      {/* Summary */}
      <p className="text-sm">
        {folders.length > 0 && `${folders.length} folder${folders.length !== 1 ? "s" : ""}, `}
        {files.length} file{files.length !== 1 ? "s" : ""}
        {totalSize > 0 && ` · ${formatSize(totalSize)} total`}
      </p>

      {/* File table */}
      <div className="border rounded-md overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/60 sticky top-0">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Name</th>
              <th className="px-3 py-2 text-right font-medium w-28">Size</th>
              <th className="px-3 py-2 text-left font-medium w-44">Modified</th>
              <th className="px-3 py-2 text-center font-medium w-24">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {/* Parent directory */}
            {currentPath !== basePath && (
              <tr className="hover:bg-muted/30 cursor-pointer" onClick={() => {
                const parent = "/" + segments.slice(0, -1).join("/")
                load(parent)
              }}>
                <td className="px-3 py-2 text-primary" colSpan={4}>📁 ..</td>
              </tr>
            )}
            {/* Folders */}
            {folders.map((f) => (
              <tr key={f.key} className="hover:bg-muted/30 cursor-pointer" onClick={() => load(f.key.replace(/\/$/, ""))}>
                <td className="px-3 py-2 text-primary flex items-center gap-2">📁 {f.name}</td>
                <td className="px-3 py-2 text-right text-muted-foreground">-</td>
                <td className="px-3 py-2 text-muted-foreground">-</td>
                <td className="px-3 py-2 text-center">-</td>
              </tr>
            ))}
            {/* Files */}
            {files.map((f) => (
              <tr key={f.key} className="hover:bg-muted/30">
                <td className="px-3 py-2 flex items-center gap-2">📄 {f.name}</td>
                <td className="px-3 py-2 text-right text-muted-foreground">{formatSize(f.size)}</td>
                <td className="px-3 py-2 text-muted-foreground text-xs">
                  {f.last_modified ? new Date(f.last_modified).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "-"}
                </td>
                <td className="px-3 py-2 text-center">
                  <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => handleDownload(f.key)}>
                    <Download className="h-3 w-3 mr-1" />Download
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Model Detail (inline) ───

function ModelDetail({
  name, onBack,
}: { name: string; onBack: () => void }) {
  const { user } = useAuth()
  const [detail, setDetail] = useState<OciModelDetail | null>(null)
  const [versions, setVersions] = useState<OciModelVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [readmeEdit, setReadmeEdit] = useState(false)
  const [readmeText, setReadmeText] = useState("")
  const [savingReadme, setSavingReadme] = useState(false)

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchOciModel(name), fetchVersions(name)])
      .then(([d, v]) => { setDetail(d); setVersions(v); setReadmeText(d.readme || "") })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [name])

  const handleSaveReadme = useCallback(async () => {
    setSavingReadme(true)
    try {
      await updateReadme(name, readmeText)
      setDetail((prev) => prev ? { ...prev, readme: readmeText } : prev)
      setReadmeEdit(false)
    } finally {
      setSavingReadme(false)
    }
  }, [name, readmeText])

  if (loading || !detail) {
    return <div className="flex items-center justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" className="h-7 px-2" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Globe className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold">{detail.display_name || detail.name}</h1>
          <SourceBadge sourceType={detail.source_type} />
        </div>
        {detail.description && <p className="text-sm text-muted-foreground ml-9">{detail.description}</p>}
        <div className="flex items-center gap-4 text-sm text-muted-foreground ml-9">
          {detail.owner && <span className="flex items-center gap-1"><User className="h-3.5 w-3.5" />{detail.owner}</span>}
          <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{timeAgo(detail.created_at)}</span>
          <span className="flex items-center gap-1"><Download className="h-3.5 w-3.5" />{detail.download_count} downloads</span>
          {detail.source_type && detail.source_type === "huggingface" && detail.source_id ? (
            <a
              href={`https://huggingface.co/${detail.source_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-primary hover:underline"
            >
              Source: huggingface:{detail.source_id} ↗
            </a>
          ) : detail.source_type ? (
            <span>Source: {detail.source_type}{detail.source_id ? `:${detail.source_id}` : ""}</span>
          ) : null}
        </div>
        {(detail.tags?.length > 0 || detail.task || detail.framework) && (
          <div className="flex flex-wrap gap-1 ml-9 mt-1">
            {detail.task && <Badge variant="secondary" className="text-xs">{detail.task}</Badge>}
            {detail.framework && <Badge variant="secondary" className="text-xs">{detail.framework}</Badge>}
            {detail.language && <Badge variant="outline" className="text-xs">{detail.language}</Badge>}
            {detail.license && <Badge variant="outline" className="text-xs">{detail.license}</Badge>}
            {detail.tags?.map((t) => (
              <Badge key={t.id} variant="outline" className="text-xs" style={{ borderColor: t.color, color: t.color }}>{t.name}</Badge>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="info">
        <TabsList variant="line">
          <TabsTrigger value="info" className="text-base">Info</TabsTrigger>
          <TabsTrigger value="model-card" className="text-base">Model Card</TabsTrigger>
          <TabsTrigger value="files" className="text-base">Files</TabsTrigger>
          <TabsTrigger value="versions" className="text-base">Versions</TabsTrigger>
          <TabsTrigger value="lineage" className="text-base">Lineage</TabsTrigger>
          <TabsTrigger value="usage" className="text-base">Usage</TabsTrigger>
          <TabsTrigger value="comments" className="text-base">Comments</TabsTrigger>
        </TabsList>

        {/* Info Tab (README + Edit) */}
        <TabsContent value="info" className="mt-4">
          <div className="flex justify-end mb-2">
            {user?.is_admin && (
              readmeEdit ? (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => { setReadmeEdit(false); setReadmeText(detail.readme || "") }} disabled={savingReadme}>Cancel</Button>
                  <Button size="sm" onClick={handleSaveReadme} disabled={savingReadme}>{savingReadme ? "Saving..." : "Save"}</Button>
                </div>
              ) : (
                <Button variant="outline" size="sm" onClick={() => setReadmeEdit(true)}>Edit</Button>
              )
            )}
          </div>
          {readmeEdit ? (
            <div className="overflow-hidden rounded" style={{ height: "calc(100vh - 320px)" }}>
              <MonacoEditor
                height="100%" language="markdown" value={readmeText}
                onChange={(v) => setReadmeText(v || "")}
                theme="light"
                options={{
                  minimap: { enabled: false }, wordWrap: "on", fontSize: 13,
                  fontFamily: "D2Coding, monospace",
                  lineNumbers: "on", renderLineHighlight: "none",
                  overviewRulerBorder: false, hideCursorInOverviewRuler: true,
                }}
              />
            </div>
          ) : detail.readme ? (
            <div className="prose prose-base max-w-none prose-headings:text-foreground prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground prose-code:text-foreground prose-code:bg-zinc-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:font-[D2Coding,monospace] [&_table]:border-collapse [&_table]:text-sm [&_th]:border [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-muted/60 [&_th]:text-foreground [&_td]:border [&_td]:px-3 [&_td]:py-1.5 [&_td]:text-foreground [&_code]:font-[D2Coding,monospace]">
              <Markdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "")
                    const codeStr = String(children).replace(/\n$/, "")
                    if (match) {
                      return (
                        <SyntaxHighlighter
                          style={oneDark}
                          language={match[1]}
                          PreTag="div"
                          customStyle={{ borderRadius: "0.5rem", fontSize: "13px", fontFamily: "D2Coding, monospace" }}
                        >
                          {codeStr}
                        </SyntaxHighlighter>
                      )
                    }
                    return <code className={className} {...props}>{children}</code>
                  },
                }}
              >
                {detail.readme}
              </Markdown>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-12">No README yet. Click <strong>Edit</strong> to write one.</p>
          )}
        </TabsContent>

        {/* Model Card (metadata from config.json) */}
        <TabsContent value="model-card" className="mt-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-sm font-medium">Model Info</CardTitle></CardHeader>
              <CardContent className="text-sm space-y-1.5">
                <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">Name</span><span>{detail.name}</span></div>
                {detail.source_id && <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">Source</span><span>{detail.source_type}: {detail.source_id}</span></div>}
                {detail.task && <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">Task</span><span>{detail.task}</span></div>}
                {detail.framework && <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">Framework</span><span>{detail.framework}</span></div>}
                {detail.language && <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">Language</span><span>{detail.language}</span></div>}
                {detail.license && <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">License</span><span>{detail.license}</span></div>}
                <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">Size</span><span>{formatSize(detail.total_size)}</span></div>
                <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">Versions</span><span>{detail.version_count}</span></div>
                <div className="flex gap-2"><span className="text-muted-foreground w-32 shrink-0">Status</span><StatusBadge status={detail.status} /></div>
              </CardContent>
            </Card>

            {versions.length > 0 && versions[0].extra_metadata && (
              <Card>
                <CardHeader><CardTitle className="text-sm font-medium">Architecture</CardTitle></CardHeader>
                <CardContent className="text-sm space-y-1.5">
                  {Object.entries(versions[0].extra_metadata as Record<string, unknown>)
                    .filter(([, v]) => v != null)
                    .map(([k, v]) => (
                      <div key={k} className="flex gap-2">
                        <span className="text-muted-foreground w-40 shrink-0">{k.replace(/_/g, " ")}</span>
                        <span className="font-mono text-xs">{Array.isArray(v) ? (v as string[]).join(", ") : String(v)}</span>
                      </div>
                    ))
                  }
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* Files */}
        <TabsContent value="files" className="mt-4">
          <FilesTab modelName={detail.name} latestVersion={detail.version_count} />
        </TabsContent>

        {/* Versions */}
        <TabsContent value="versions" className="mt-4">
          {versions.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No versions yet.</p>
          ) : (
            <div className="border rounded-md overflow-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/60 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium w-20">Version</th>
                    <th className="px-3 py-2 text-center font-medium w-20">Files</th>
                    <th className="px-3 py-2 text-center font-medium w-24">Size</th>
                    <th className="px-3 py-2 text-center font-medium w-24">Status</th>
                    <th className="px-3 py-2 text-left font-medium">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {versions.map((v) => (
                    <tr key={v.id} className="hover:bg-muted/30">
                      <td className="px-3 py-2">v{v.version}</td>
                      <td className="px-3 py-2 text-center">{v.file_count}</td>
                      <td className="px-3 py-2 text-center">{formatSize(v.total_size)}</td>
                      <td className="px-3 py-2 text-center"><StatusBadge status={v.status} /></td>
                      <td className="px-3 py-2">{timeAgo(v.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        {/* Lineage */}
        <TabsContent value="lineage" className="mt-4">
          <LineageGraph modelName={detail.name} lineage={detail.lineage} />
        </TabsContent>

        {/* Usage */}
        <TabsContent value="usage" className="mt-4">
          <div className="h-[400px] overflow-hidden rounded">
            <MonacoEditor
              height="100%" language="python"
              value={`from argus_catalog_sdk import ModelClient

client = ModelClient("http://<argus-catalog-server>:<argus-catalog-server-port>")

# Pull model to local directory
client.pull("${detail.name}", version=${detail.version_count || 1}, dest="/tmp/${detail.name}")

# Or get presigned download URLs
urls = client.get_download_urls("${detail.name}", version=${detail.version_count || 1})
for filename, url in urls["files"].items():
    print(f"{filename}: {url}")
`}
              theme="light"
              options={{
                readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false,
                fontSize: 13, fontFamily: "D2Coding, monospace", lineNumbers: "on",
                domReadOnly: true, renderLineHighlight: "none",
                overviewRulerBorder: false, hideCursorInOverviewRuler: true,
              }}
            />
          </div>
        </TabsContent>

        {/* Comments */}
        <TabsContent value="comments" className="mt-4">
          <CommentSection entityType="oci-model" entityId={detail.name} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// ─── Main Page ───

// ─── HuggingFace URL validation ───

const HF_URL_REGEX = /^https?:\/\/huggingface\.co\/([a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_.-]+)?)(?:\/.*)?$/

function extractHfModelId(url: string): string | null {
  // Accept both URL and direct model ID
  const urlMatch = HF_URL_REGEX.exec(url.trim())
  if (urlMatch) return urlMatch[1]
  // Direct model ID: org/model or model
  const directMatch = /^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_.-]+)?$/.exec(url.trim())
  if (directMatch) return directMatch[0]
  return null
}

// ─── Main Page ───

export default function OciHubPage() {
  const { user } = useAuth()
  const [models, setModels] = useState<OciModelSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState("dashboard")
  const [viewMode, setViewMode] = useState<"card" | "list">("card")
  const [guideOpen, setGuideOpen] = useState(false)
  const [guideTab, setGuideTab] = useState<"cli" | "sdk" | "api">("cli")
  const [useGuideOpen, setUseGuideOpen] = useState(false)
  const [useGuideTab, setUseGuideTab] = useState<"cli" | "sdk" | "api">("cli")
  const [serverHost, setServerHost] = useState("")
  const [serverPort, setServerPort] = useState(4600)
  const pageSize = 12
  const totalPages = Math.ceil(total / pageSize)

  // Import dialog state
  const [importOpen, setImportOpen] = useState(false)
  const [importUrl, setImportUrl] = useState("")
  const [importing, setImporting] = useState(false)
  const [importProgress, setImportProgress] = useState(0)
  const [importError, setImportError] = useState<string | null>(null)
  const [importSuccess, setImportSuccess] = useState<string | null>(null)

  const extractedId = extractHfModelId(importUrl)
  const isValidUrl = !!extractedId

  // Fetch server info for guide code examples
  useEffect(() => {
    if ((guideOpen || useGuideOpen) && !serverHost) {
      fetch("/api/v1/oci-models/server-info")
        .then((r) => r.json())
        .then((d) => { setServerHost(d.host); setServerPort(d.port) })
        .catch(() => { setServerHost("localhost"); setServerPort(4600) })
    }
  }, [guideOpen, useGuideOpen, serverHost])

  const serverUrl = `http://${serverHost || "localhost"}:${serverPort}`

  const load = useCallback(async (p: number, s: string) => {
    setLoading(true)
    try {
      const data = await fetchOciModels({ search: s || undefined, page: p, pageSize })
      setModels(data.items)
      setTotal(data.total)
      setPage(p)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(1, "") }, [load])

  const handleImport = useCallback(async () => {
    if (!extractedId) return
    setImporting(true)
    setImportError(null)
    setImportSuccess(null)
    setImportProgress(10)

    try {
      // Simulate progress (actual import is a single request)
      const progressInterval = setInterval(() => {
        setImportProgress((prev) => Math.min(prev + 5, 85))
      }, 500)

      const result = await importFromHuggingFace({
        hf_model_id: extractedId,
        name: extractedId.replace(/\//g, "-"),
      })

      clearInterval(progressInterval)
      setImportProgress(100)
      setImportSuccess(
        `Imported ${result.name} v${result.version}: ${result.file_count} files, ${formatSize(result.total_size)}`
      )

      // Reload list after short delay
      setTimeout(() => {
        setImportOpen(false)
        setImportUrl("")
        setImportProgress(0)
        setImportSuccess(null)
        load(1, search)
      }, 2000)
    } catch (e) {
      setImportError(e instanceof Error ? e.message : "Import failed")
      setImportProgress(0)
    } finally {
      setImporting(false)
    }
  }, [extractedId, load, search])

  function handleImportClose(open: boolean) {
    if (!importing) {
      setImportOpen(open)
      if (!open) {
        setImportUrl("")
        setImportError(null)
        setImportSuccess(null)
        setImportProgress(0)
      }
    }
  }

  return (
    <>
      <DashboardHeader title="OCI Model Hub" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Tabs value={selectedModel ? "models" : activeTab} onValueChange={(v) => { setActiveTab(v); setSelectedModel(null) }}>
          <TabsList variant="line">
            <TabsTrigger value="dashboard" className="text-base">Dashboard</TabsTrigger>
            <TabsTrigger value="models" className="text-base">Models</TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="mt-4">
            <OciHubDashboard />
          </TabsContent>

          <TabsContent value="models" className="mt-4">
          {selectedModel ? (
            <ModelDetail name={selectedModel} onBack={() => { setSelectedModel(null); load(page, search) }} />
          ) : (
        <div className="space-y-4">
        {/* Toolbar */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search models..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load(1, search)}
              className="pl-8 h-9"
            />
          </div>
          {search && (
            <Button variant="ghost" size="sm" onClick={() => { setSearch(""); load(1, "") }}>
              <X className="h-3.5 w-3.5 mr-1" />Clear
            </Button>
          )}
          <div className="flex items-center gap-2 ml-auto">
            {/* View toggle */}
            <div className="flex items-center border rounded-md">
              <Button
                variant={viewMode === "card" ? "secondary" : "ghost"}
                size="icon-sm"
                onClick={() => setViewMode("card")}
                aria-label="Card view"
              >
                <Grid3X3 className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant={viewMode === "list" ? "secondary" : "ghost"}
                size="icon-sm"
                onClick={() => setViewMode("list")}
                aria-label="List view"
              >
                <List className="h-3.5 w-3.5" />
              </Button>
            </div>
            {user?.is_admin && (
              <Button size="sm" onClick={() => setImportOpen(true)}>
                <Import className="h-4 w-4 mr-1.5" />
                Import from HuggingFace
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setGuideOpen(true)}>
              <BookOpen className="h-4 w-4 mr-1.5" />
              How to Import
            </Button>
            <Button variant="outline" size="sm" onClick={() => setUseGuideOpen(true)}>
              <Code2 className="h-4 w-4 mr-1.5" />
              How to Use
            </Button>
          </div>
        </div>

        {/* Import Dialog */}
        <Dialog open={importOpen} onOpenChange={handleImportClose}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Import from HuggingFace</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="grid gap-2">
                <Label>HuggingFace URL or Model ID</Label>
                <Input
                  value={importUrl}
                  onChange={(e) => { setImportUrl(e.target.value); setImportError(null) }}
                  placeholder="https://huggingface.co/bert-base-uncased"
                  disabled={importing}
                />
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>Accepted formats:</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    <li><code>https://huggingface.co/bert-base-uncased</code></li>
                    <li><code>https://huggingface.co/meta-llama/Llama-3.1-8B</code></li>
                    <li><code>bert-base-uncased</code> (model ID directly)</li>
                    <li><code>meta-llama/Llama-3.1-8B</code> (org/model directly)</li>
                  </ul>
                </div>
                {extractedId && (
                  <p className="text-sm text-primary">
                    Model ID: <strong>{extractedId}</strong>
                  </p>
                )}
              </div>

              {/* Progress bar */}
              {(importing || importProgress > 0) && (
                <div className="space-y-1">
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        importSuccess ? "bg-green-500" : "bg-primary"
                      }`}
                      style={{ width: `${importProgress}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {importing ? "Downloading and uploading to S3..." : importProgress === 100 ? "Complete!" : ""}
                  </p>
                </div>
              )}

              {importError && <p className="text-sm text-destructive">{importError}</p>}
              {importSuccess && <p className="text-sm text-green-600">{importSuccess}</p>}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => handleImportClose(false)} disabled={importing}>
                  Cancel
                </Button>
                <Button onClick={handleImport} disabled={!isValidUrl || importing}>
                  {importing ? (
                    <><Loader2 className="h-4 w-4 animate-spin mr-1.5" />Importing...</>
                  ) : (
                    "Import"
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* How to Import Guide Dialog */}
        <Dialog open={guideOpen} onOpenChange={setGuideOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>How to Import Models</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {/* Tab buttons */}
              <div className="flex items-center border rounded-md w-fit">
                {(["cli", "sdk", "api"] as const).map((t) => (
                  <Button
                    key={t}
                    variant={guideTab === t ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => setGuideTab(t)}
                    className="rounded-none first:rounded-l-md last:rounded-r-md"
                  >
                    {t === "cli" ? "CLI" : t === "sdk" ? "Python SDK" : "REST API"}
                  </Button>
                ))}
              </div>

              {/* CLI tab */}
              {guideTab === "cli" && (
                <div className="h-[520px] overflow-hidden rounded">
                  <MonacoEditor
                    height="100%" language="shell"
                    value={`# ─── Install CLI ───
pip install argus-catalog-sdk

# ─── Import from HuggingFace ───
argus-model import-hf bert-base-uncased my-bert \\
  --server ${serverUrl} \\
  --description "BERT base model"

# ─── Import from local directory (airgap) ───
# 1. Transfer model files to server via USB/SCP
# 2. Import from server-local path
argus-model import-local /data/transferred/bert my-bert \\
  --server ${serverUrl}

# ─── Push local model via presigned URLs ───
# (uploads from client machine, no server filesystem access needed)
argus-model push /path/to/my-model my-custom-model \\
  --server ${serverUrl} \\
  --description "My custom trained model"

# ─── List imported models ───
argus-model list --server ${serverUrl}

# ─── Pull model to local ───
argus-model pull my-bert 1 /tmp/my-bert --server ${serverUrl}`}
                    theme="light"
                    options={{
                      readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false,
                      fontSize: 13, fontFamily: "D2Coding, monospace", lineNumbers: "on",
                      domReadOnly: true, renderLineHighlight: "none",
                      overviewRulerBorder: false, hideCursorInOverviewRuler: true,
                    }}
                  />
                </div>
              )}

              {/* Python SDK tab */}
              {guideTab === "sdk" && (
                <div className="h-[520px] overflow-hidden rounded">
                  <MonacoEditor
                    height="100%" language="python"
                    value={`from argus_catalog_sdk import ModelClient

client = ModelClient("${serverUrl}")

# ─── Import from HuggingFace ───
result = client.import_huggingface(
    "bert-base-uncased",
    "my-bert",
    description="BERT base model",
    owner="ml-team",
)
print(f"Imported v{result['version']}: {result['file_count']} files")

# ─── Import from local directory (airgap) ───
# The directory must be accessible to the catalog server
result = client.import_local(
    "/data/transferred/bert",
    "my-bert",
    description="BERT (airgap import)",
)

# ─── Push local model via presigned URLs ───
# Uploads from client side (no server filesystem access needed)
result = client.push(
    "/path/to/my-model",
    "my-custom-model",
    description="My custom trained model",
)

# ─── List models ───
models = client.list_models()
for m in models["items"]:
    print(f"{m['name']} - v{m['max_version_number']}")

# ─── Pull model to local ───
files = client.pull("my-bert", version=1, dest="/tmp/my-bert")
print(f"Downloaded {len(files)} files")`}
                    theme="light"
                    options={{
                      readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false,
                      fontSize: 13, fontFamily: "D2Coding, monospace", lineNumbers: "on",
                      domReadOnly: true, renderLineHighlight: "none",
                      overviewRulerBorder: false, hideCursorInOverviewRuler: true,
                    }}
                  />
                </div>
              )}

              {/* REST API tab */}
              {guideTab === "api" && (
                <div className="h-[520px] overflow-hidden rounded">
                  <MonacoEditor
                    height="100%" language="shell"
                    value={`# ─── Import from HuggingFace ───
curl -X POST "${serverUrl}/api/v1/oci-models/import/huggingface" \\
  -H "Content-Type: application/json" \\
  -d '{
    "hf_model_id": "bert-base-uncased",
    "name": "my-bert",
    "description": "BERT base model",
    "owner": "ml-team",
    "task": "fill-mask",
    "framework": "pytorch"
  }'

# ─── Create model manually ───
curl -X POST "${serverUrl}/api/v1/oci-models" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "my-custom-model",
    "description": "My custom model",
    "task": "classification",
    "framework": "sklearn"
  }'

# ─── List models ───
curl "${serverUrl}/api/v1/oci-models?page=1&page_size=10"

# ─── Get model detail ───
curl "${serverUrl}/api/v1/oci-models/my-bert"

# ─── Update README ───
curl -X PUT "${serverUrl}/api/v1/oci-models/my-bert/readme" \\
  -H "Content-Type: application/json" \\
  -d '{"readme": "# My BERT Model\\n\\nThis is my model."}'`}
                    theme="light"
                    options={{
                      readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false,
                      fontSize: 13, fontFamily: "D2Coding, monospace", lineNumbers: "on",
                      domReadOnly: true, renderLineHighlight: "none",
                      overviewRulerBorder: false, hideCursorInOverviewRuler: true,
                    }}
                  />
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* How to Use Guide Dialog */}
        <Dialog open={useGuideOpen} onOpenChange={setUseGuideOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>How to Use Models</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="flex items-center border rounded-md w-fit">
                {(["cli", "sdk", "api"] as const).map((t) => (
                  <Button
                    key={t}
                    variant={useGuideTab === t ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => setUseGuideTab(t)}
                    className="rounded-none first:rounded-l-md last:rounded-r-md"
                  >
                    {t === "cli" ? "CLI" : t === "sdk" ? "Python SDK" : "REST API"}
                  </Button>
                ))}
              </div>

              {useGuideTab === "cli" && (
                <div className="h-[520px] overflow-hidden rounded">
                  <MonacoEditor
                    height="100%" language="shell"
                    value={`# ─── Install CLI ───
pip install argus-catalog-sdk

# ─── List available models ───
argus-model list --server ${serverUrl}

# ─── Pull model to local directory ───
argus-model pull my-bert 1 /tmp/my-bert --server ${serverUrl}

# Files will be downloaded:
#   /tmp/my-bert/config.json
#   /tmp/my-bert/model.safetensors
#   /tmp/my-bert/tokenizer.json
#   ...

# ─── List files in a model version ───
argus-model files my-bert 1 --server ${serverUrl}

# ─── View OCI manifest ───
argus-model manifest my-bert 1 --server ${serverUrl}

# ─── Use the downloaded model ───
# After pulling, load it with your framework:
python -c "
from transformers import AutoModel, AutoTokenizer
model = AutoModel.from_pretrained('/tmp/my-bert')
tokenizer = AutoTokenizer.from_pretrained('/tmp/my-bert')
inputs = tokenizer('Hello world', return_tensors='pt')
outputs = model(**inputs)
print('Output shape:', outputs.last_hidden_state.shape)
"`}
                    theme="light"
                    options={{
                      readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false,
                      fontSize: 13, fontFamily: "D2Coding, monospace", lineNumbers: "on",
                      domReadOnly: true, renderLineHighlight: "none",
                      overviewRulerBorder: false, hideCursorInOverviewRuler: true,
                    }}
                  />
                </div>
              )}

              {useGuideTab === "sdk" && (
                <div className="h-[520px] overflow-hidden rounded">
                  <MonacoEditor
                    height="100%" language="python"
                    value={`from argus_catalog_sdk import ModelClient

client = ModelClient("${serverUrl}")

# ─── List available models ───
models = client.list_models()
for m in models["items"]:
    print(f"{m['name']} v{m['max_version_number']} - {m['status']}")

# ─── Pull model to local directory ───
files = client.pull("my-bert", version=1, dest="/tmp/my-bert")
print(f"Downloaded {len(files)} files to /tmp/my-bert")

# ─── Get presigned download URLs ───
# (for selective download or integration with other tools)
urls = client.get_download_urls("my-bert", version=1)
for filename, url in urls["files"].items():
    print(f"{filename}: {url}")

# ─── Use with HuggingFace Transformers ───
from transformers import AutoModel, AutoTokenizer

model = AutoModel.from_pretrained("/tmp/my-bert")
tokenizer = AutoTokenizer.from_pretrained("/tmp/my-bert")

inputs = tokenizer("Hello world", return_tensors="pt")
outputs = model(**inputs)
print("Output shape:", outputs.last_hidden_state.shape)

# ─── Use with PyTorch directly ───
import torch
state_dict = torch.load("/tmp/my-bert/pytorch_model.bin", weights_only=True)
print(f"Loaded {len(state_dict)} parameter tensors")

# ─── Use with ONNX Runtime ───
import onnxruntime as ort
session = ort.InferenceSession("/tmp/my-bert/onnx/model.onnx")
print("ONNX model loaded, inputs:", [i.name for i in session.get_inputs()])`}
                    theme="light"
                    options={{
                      readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false,
                      fontSize: 13, fontFamily: "D2Coding, monospace", lineNumbers: "on",
                      domReadOnly: true, renderLineHighlight: "none",
                      overviewRulerBorder: false, hideCursorInOverviewRuler: true,
                    }}
                  />
                </div>
              )}

              {useGuideTab === "api" && (
                <div className="h-[520px] overflow-hidden rounded">
                  <MonacoEditor
                    height="100%" language="shell"
                    value={`# ─── List available models ───
curl "${serverUrl}/api/v1/oci-models?page=1&page_size=10"

# ─── Get model detail ───
curl "${serverUrl}/api/v1/oci-models/my-bert"

# ─── Get model versions ───
curl "${serverUrl}/api/v1/oci-models/my-bert/versions"

# ─── Get presigned download URLs for all files ───
curl "${serverUrl}/api/v1/model-store/my-bert/versions/1/download-urls"
# Response: {"files": {"config.json": "https://minio/...", "model.safetensors": "https://..."}}

# ─── Download a specific file ───
curl "${serverUrl}/api/v1/model-store/my-bert/versions/1/download-url?filename=config.json"
# Response: {"url": "https://minio/...presigned...", "key": "...", "expires_in": 3600}

# Then download the file directly:
curl -o config.json "<presigned_url_from_above>"

# ─── Browse S3 bucket ───
curl "${serverUrl}/api/v1/model-store/browse/list?path=/my-bert/v1"

# ─── Get OCI manifest ───
curl "${serverUrl}/api/v1/model-store/my-bert/versions/1/manifest"`}
                    theme="light"
                    options={{
                      readOnly: true, minimap: { enabled: false }, scrollBeyondLastLine: false,
                      fontSize: 13, fontFamily: "D2Coding, monospace", lineNumbers: "on",
                      domReadOnly: true, renderLineHighlight: "none",
                      overviewRulerBorder: false, hideCursorInOverviewRuler: true,
                    }}
                  />
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Content */}
        {loading ? (
          <div className="text-center py-12 text-muted-foreground">Loading models...</div>
        ) : models.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            No models found.{" "}
            <span className="text-primary">Import from HuggingFace</span> or push via SDK.
          </div>
        ) : viewMode === "card" ? (
          /* Card View (3 columns) */
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {models.map((m) => (
              <ModelCard key={m.id} model={m} onClick={() => setSelectedModel(m.name)} />
            ))}
          </div>
        ) : (
          /* List View (table) */
          <div className="border rounded-md overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Name</th>
                  <th className="px-3 py-2 text-left font-medium w-48">Description</th>
                  <th className="px-3 py-2 text-center font-medium w-24">Task</th>
                  <th className="px-3 py-2 text-center font-medium w-24">Framework</th>
                  <th className="px-3 py-2 text-center font-medium w-24">Size</th>
                  <th className="px-3 py-2 text-center font-medium w-16">Ver</th>
                  <th className="px-3 py-2 text-center font-medium w-24">Source</th>
                  <th className="px-3 py-2 text-center font-medium w-24">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {models.map((m) => (
                  <tr
                    key={m.id}
                    className="hover:bg-muted/30 cursor-pointer"
                    onClick={() => setSelectedModel(m.name)}
                  >
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Box className="h-4 w-4 text-primary shrink-0" />
                        <span className="font-medium truncate max-w-[250px]" title={m.display_name || m.name}>
                          {m.display_name || m.name}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground truncate max-w-[200px]" title={m.description || ""}>
                      {m.description || "-"}
                    </td>
                    <td className="px-3 py-2 text-center">{m.task || "-"}</td>
                    <td className="px-3 py-2 text-center">{m.framework || "-"}</td>
                    <td className="px-3 py-2 text-center">{formatSize(m.total_size)}</td>
                    <td className="px-3 py-2 text-center">v{m.version_count}</td>
                    <td className="px-3 py-2 text-center"><SourceBadge sourceType={m.source_type} /></td>
                    <td className="px-3 py-2 text-center text-muted-foreground">{timeAgo(m.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-1 pt-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => load(page - 1, search)}>Previous</Button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <Button key={p} variant={p === page ? "default" : "outline"} size="sm" className="w-8 h-8 p-0" onClick={() => load(p, search)}>{p}</Button>
            ))}
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => load(page + 1, search)}>Next</Button>
          </div>
        )}
        </div>
          )}
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
