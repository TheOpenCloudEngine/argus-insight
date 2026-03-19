"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  ChevronRight,
  Database,
  FolderOpen,
  FunctionSquare,
  Library,
  Loader2,
  Table2,
  Brain,
  HardDrive,
} from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { listCatalogs, listSchemas, listTables, listVolumes, listFunctions, listModels } from "../api"
import type { Catalog, Schema, UCTable, Volume, UCFunction, Model } from "../data/schema"

const UC_BASE = "/dashboard/unity-catalog"

type TreeNodeProps = {
  label: string
  icon: React.ReactNode
  href?: string
  isActive?: boolean
  expandable?: boolean
  expanded?: boolean
  onToggle?: () => void
  depth?: number
  children?: React.ReactNode
}

function TreeNode({ label, icon, href, isActive, expandable, expanded, onToggle, depth = 0, children }: TreeNodeProps) {
  const content = (
    <div
      className={cn(
        "flex items-center gap-1.5 rounded-md px-2 py-1 text-sm transition-colors",
        isActive ? "bg-accent text-accent-foreground font-medium" : "hover:bg-muted text-foreground",
      )}
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
    >
      {expandable ? (
        <button type="button" onClick={onToggle} className="shrink-0 p-0.5">
          <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", expanded && "rotate-90")} />
        </button>
      ) : (
        <span className="w-4" />
      )}
      <span className="shrink-0">{icon}</span>
      <span className="truncate">{label}</span>
    </div>
  )

  return (
    <div>
      {href ? (
        <Link href={href} className="block">
          {content}
        </Link>
      ) : (
        <div className="cursor-pointer" onClick={onToggle}>
          {content}
        </div>
      )}
      {expanded && children}
    </div>
  )
}

type EntityGroupProps = {
  label: string
  icon: React.ReactNode
  items: { name: string; href: string }[]
  loading?: boolean
  depth: number
  pathname: string
}

function EntityGroup({ label, icon, items, loading, depth, pathname }: EntityGroupProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <TreeNode
      label={label}
      icon={icon}
      expandable
      expanded={expanded}
      onToggle={() => setExpanded(!expanded)}
      depth={depth}
    >
      {loading ? (
        <div className="flex items-center gap-2 py-1" style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}>
          <Loader2 className="h-3 w-3 animate-spin" />
          <span className="text-foreground/70 text-xs">Loading...</span>
        </div>
      ) : items.length > 0 ? (
        items.map((item) => (
          <TreeNode
            key={item.name}
            label={item.name}
            icon={icon}
            href={item.href}
            isActive={pathname === item.href}
            depth={depth + 1}
          />
        ))
      ) : (
        <div className="text-muted-foreground py-1 text-xs" style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}>
          No items
        </div>
      )}
    </TreeNode>
  )
}

type SchemaNodeProps = {
  catalog: string
  schema: Schema
  depth: number
  pathname: string
}

function SchemaNode({ catalog, schema, depth, pathname }: SchemaNodeProps) {
  const [expanded, setExpanded] = useState(false)
  const [tables, setTables] = useState<UCTable[]>([])
  const [volumes, setVolumes] = useState<Volume[]>([])
  const [functions, setFunctions] = useState<UCFunction[]>([])
  const [models, setModels] = useState<Model[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    if (loaded) return
    setLoading(true)
    try {
      const [t, v, f, m] = await Promise.all([
        listTables(catalog, schema.name),
        listVolumes(catalog, schema.name),
        listFunctions(catalog, schema.name),
        listModels(catalog, schema.name),
      ])
      setTables(t)
      setVolumes(v)
      setFunctions(f)
      setModels(m)
      setLoaded(true)
    } finally {
      setLoading(false)
    }
  }, [catalog, schema.name, loaded])

  function handleToggle() {
    if (!expanded) loadData()
    setExpanded(!expanded)
  }

  const schemaHref = `${UC_BASE}/schemas/${catalog}/${schema.name}`

  return (
    <TreeNode
      label={schema.name}
      icon={<Database className="h-3.5 w-3.5" />}
      href={schemaHref}
      isActive={pathname === schemaHref}
      expandable
      expanded={expanded}
      onToggle={handleToggle}
      depth={depth}
    >
      {loading ? (
        <div className="flex items-center gap-2 py-1" style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}>
          <Loader2 className="h-3 w-3 animate-spin" />
          <span className="text-foreground/70 text-xs">Loading...</span>
        </div>
      ) : (
        <>
          <EntityGroup
            label="Tables"
            icon={<Table2 className="h-3.5 w-3.5" />}
            items={tables.map((t) => ({ name: t.name, href: `${UC_BASE}/tables/${catalog}/${schema.name}/${t.name}` }))}
            depth={depth + 1}
            pathname={pathname}
          />
          <EntityGroup
            label="Volumes"
            icon={<HardDrive className="h-3.5 w-3.5" />}
            items={volumes.map((v) => ({ name: v.name, href: `${UC_BASE}/volumes/${catalog}/${schema.name}/${v.name}` }))}
            depth={depth + 1}
            pathname={pathname}
          />
          <EntityGroup
            label="Functions"
            icon={<FunctionSquare className="h-3.5 w-3.5" />}
            items={functions.map((f) => ({ name: f.name, href: `${UC_BASE}/functions/${catalog}/${schema.name}/${f.name}` }))}
            depth={depth + 1}
            pathname={pathname}
          />
          <EntityGroup
            label="Models"
            icon={<Brain className="h-3.5 w-3.5" />}
            items={models.map((m) => ({ name: m.name, href: `${UC_BASE}/models/${catalog}/${schema.name}/${m.name}` }))}
            depth={depth + 1}
            pathname={pathname}
          />
        </>
      )}
    </TreeNode>
  )
}

type CatalogNodeProps = {
  catalog: Catalog
  depth: number
  pathname: string
}

function CatalogNode({ catalog, depth, pathname }: CatalogNodeProps) {
  const [expanded, setExpanded] = useState(false)
  const [schemas, setSchemas] = useState<Schema[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)

  const loadSchemas = useCallback(async () => {
    if (loaded) return
    setLoading(true)
    try {
      const data = await listSchemas(catalog.name)
      setSchemas(data)
      setLoaded(true)
    } finally {
      setLoading(false)
    }
  }, [catalog.name, loaded])

  function handleToggle() {
    if (!expanded) loadSchemas()
    setExpanded(!expanded)
  }

  const catalogHref = `${UC_BASE}/catalogs/${catalog.name}`

  return (
    <TreeNode
      label={catalog.name}
      icon={<Library className="h-3.5 w-3.5" />}
      href={catalogHref}
      isActive={pathname === catalogHref}
      expandable
      expanded={expanded}
      onToggle={handleToggle}
      depth={depth}
    >
      {loading ? (
        <div className="flex items-center gap-2 py-1" style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}>
          <Loader2 className="h-3 w-3 animate-spin" />
          <span className="text-foreground/70 text-xs">Loading...</span>
        </div>
      ) : schemas.length > 0 ? (
        schemas.map((schema) => (
          <SchemaNode
            key={schema.name}
            catalog={catalog.name}
            schema={schema}
            depth={depth + 1}
            pathname={pathname}
          />
        ))
      ) : loaded ? (
        <div className="text-muted-foreground py-1 text-xs" style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}>
          No schemas
        </div>
      ) : null}
    </TreeNode>
  )
}

export function UCSchemaB() {
  const pathname = usePathname()
  const [catalogs, setCatalogs] = useState<Catalog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listCatalogs()
      .then(setCatalogs)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load catalogs"))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="pr-2 text-black dark:text-white" style={{ fontSize: '120%' }}>
      <div className="mb-2 px-2 text-sm font-semibold uppercase tracking-wider">
        Schema Browser
      </div>
      {loading ? (
        <div className="flex items-center gap-2 px-2 py-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          <span className="text-foreground/70 text-sm">Loading catalogs...</span>
        </div>
      ) : error ? (
        <p className="text-destructive px-2 text-xs">{error}</p>
      ) : catalogs.length > 0 ? (
        catalogs.map((cat) => (
          <CatalogNode key={cat.name} catalog={cat} depth={0} pathname={pathname} />
        ))
      ) : (
        <p className="text-muted-foreground px-2 text-sm">No catalogs found.</p>
      )}
    </div>
  )
}
