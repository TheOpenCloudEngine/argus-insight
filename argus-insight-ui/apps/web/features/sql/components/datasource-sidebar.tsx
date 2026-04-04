"use client"

import React, { useCallback, useEffect, useState } from "react"
import {
  ChevronRight,
  Columns3,
  Database,
  FolderOpen,
  Loader2,

  RefreshCw,
  Table2,
} from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@workspace/ui/components/tooltip"
import * as api from "../api"
import type { CatalogNode, ColumnNode, SchemaNode, TableNode } from "../types"
import { useSql } from "./sql-provider"

// ---------------------------------------------------------------------------
// Tree node types
// ---------------------------------------------------------------------------

interface TreeNodeState {
  expanded: boolean
  loading: boolean
  children?: TreeNodeState[]
  type: "datasource" | "catalog" | "schema" | "table" | "column"
  label: string
  meta?: Record<string, string>
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DatasourceSidebar() {
  const { workspaceDatasources, activeDatasource, setActiveDatasource, refreshWorkspaceDatasources } =
    useSql()

  return (
    <div className="flex h-full min-h-0 flex-col border-r overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b shrink-0">
        <span className="text-xs font-semibold uppercase text-muted-foreground">Datasources</span>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={refreshWorkspaceDatasources}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">Refresh</TooltipContent>
        </Tooltip>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="p-1">
          {workspaceDatasources.length === 0 && (
            <p className="px-3 py-4 text-center text-sm text-muted-foreground">
              No datasources in this workspace.
            </p>
          )}
          {workspaceDatasources.map((ds) => (
            <DatasourceTreeNode
              key={`ws-${ds.id}`}
              datasource={ds}
              isActive={activeDatasource?.id === ds.id}
              onSelect={() => setActiveDatasource(ds)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Datasource tree node (expandable: catalogs → schemas → tables → columns)
// ---------------------------------------------------------------------------

function DatasourceTreeNode({
  datasource,
  isActive,
  onSelect,
}: {
  datasource: api.Datasource
  isActive: boolean
  onSelect: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [catalogs, setCatalogs] = useState<CatalogNode[] | null>(null)
  const [loading, setLoading] = useState(false)

  const toggle = useCallback(async () => {
    onSelect()
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (!catalogs) {
      setLoading(true)
      try {
        const cats = await api.fetchCatalogs(datasource.id)
        setCatalogs(cats)
      } catch {
        setCatalogs([])
      } finally {
        setLoading(false)
      }
    }
  }, [expanded, catalogs, datasource.id, onSelect])

  const engineBadge: Record<string, string> = {
    trino: "T",
    starrocks: "SR",
    postgresql: "PG",
    mariadb: "MY",
  }

  return (
    <div>
      <button
        onClick={toggle}
        className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted/50 ${
          isActive ? "bg-muted" : ""
        }`}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform ${
            expanded ? "rotate-90" : ""
          }`}
        />
        <Database className="h-3.5 w-3.5 shrink-0 text-blue-500" />
        <span className="truncate font-medium">{datasource.name}</span>
        <span className="ml-auto shrink-0 rounded bg-muted px-1 text-[10px] font-semibold text-muted-foreground">
          {engineBadge[datasource.engine_type] || datasource.engine_type}
        </span>
      </button>

      {expanded && (
        <div className="ml-4">
          {loading && (
            <div className="flex items-center gap-1.5 px-2 py-1 text-sm text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Loading...
            </div>
          )}
          {catalogs &&
            catalogs.length > 0 &&
            catalogs.map((cat) => (
              <CatalogTreeNode key={cat.name} dsId={datasource.id} catalog={cat} />
            ))}
          {catalogs && catalogs.length === 0 && !loading && (
            <SchemaList dsId={datasource.id} catalog="" />
          )}
        </div>
      )}
    </div>
  )
}

function CatalogTreeNode({ dsId, catalog }: { dsId: number; catalog: CatalogNode }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-sm hover:bg-muted/50"
      >
        <ChevronRight
          className={`h-3 w-3 shrink-0 text-muted-foreground transition-transform ${
            expanded ? "rotate-90" : ""
          }`}
        />
        <FolderOpen className="h-3 w-3 shrink-0 text-amber-500" />
        <span className="truncate">{catalog.name}</span>
      </button>
      {expanded && <SchemaList dsId={dsId} catalog={catalog.name} />}
    </div>
  )
}

function SchemaList({ dsId, catalog }: { dsId: number; catalog: string }) {
  const [schemas, setSchemas] = useState<SchemaNode[] | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api
      .fetchSchemas(dsId, catalog)
      .then(setSchemas)
      .catch(() => setSchemas([]))
      .finally(() => setLoading(false))
  }, [dsId, catalog])

  if (loading)
    return (
      <div className="ml-4 flex items-center gap-1.5 px-2 py-1 text-sm text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" /> Loading schemas...
      </div>
    )

  return (
    <div className="ml-3">
      {schemas?.map((s) => (
        <SchemaTreeNode key={s.name} dsId={dsId} catalog={catalog} schema={s} />
      ))}
    </div>
  )
}

function SchemaTreeNode({
  dsId,
  catalog,
  schema,
}: {
  dsId: number
  catalog: string
  schema: SchemaNode
}) {
  const [expanded, setExpanded] = useState(false)
  const [tables, setTables] = useState<TableNode[] | null>(null)
  const [loading, setLoading] = useState(false)

  const toggle = useCallback(async () => {
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (!tables) {
      setLoading(true)
      try {
        setTables(await api.fetchTables(dsId, catalog, schema.name))
      } catch {
        setTables([])
      } finally {
        setLoading(false)
      }
    }
  }, [expanded, tables, dsId, catalog, schema.name])

  return (
    <div>
      <button
        onClick={toggle}
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-sm hover:bg-muted/50"
      >
        <ChevronRight
          className={`h-3 w-3 shrink-0 text-muted-foreground transition-transform ${
            expanded ? "rotate-90" : ""
          }`}
        />
        <FolderOpen className="h-3 w-3 shrink-0 text-purple-500" />
        <span className="truncate">{schema.name}</span>
      </button>
      {expanded && (
        <div className="ml-3">
          {loading && (
            <div className="flex items-center gap-1.5 px-2 py-1 text-sm text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
            </div>
          )}
          {tables?.map((t) => (
            <TableTreeNode
              key={t.name}
              dsId={dsId}
              catalog={catalog}
              schema={schema.name}
              table={t}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TableTreeNode({
  dsId,
  catalog,
  schema,
  table,
}: {
  dsId: number
  catalog: string
  schema: string
  table: TableNode
}) {
  const [expanded, setExpanded] = useState(false)
  const [columns, setColumns] = useState<ColumnNode[] | null>(null)
  const [loading, setLoading] = useState(false)

  const toggle = useCallback(async () => {
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (!columns) {
      setLoading(true)
      try {
        setColumns(await api.fetchColumns(dsId, table.name, catalog, schema))
      } catch {
        setColumns([])
      } finally {
        setLoading(false)
      }
    }
  }, [expanded, columns, dsId, catalog, schema, table.name])

  const isView = table.table_type?.toUpperCase().includes("VIEW")

  return (
    <div>
      <button
        onClick={toggle}
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-sm hover:bg-muted/50"
      >
        <ChevronRight
          className={`h-3 w-3 shrink-0 text-muted-foreground transition-transform ${
            expanded ? "rotate-90" : ""
          }`}
        />
        <Table2 className={`h-3 w-3 shrink-0 ${isView ? "text-teal-500" : "text-green-500"}`} />
        <span className="truncate">{table.name}</span>
        {isView && (
          <span className="ml-auto text-[10px] text-muted-foreground">VIEW</span>
        )}
      </button>
      {expanded && (
        <div className="ml-3">
          {loading && (
            <div className="flex items-center gap-1.5 px-2 py-1 text-sm text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
            </div>
          )}
          {columns?.map((col) => (
            <div
              key={col.name}
              className="flex items-center gap-1.5 px-2 py-0.5 text-sm text-muted-foreground"
            >
              <Columns3 className="h-3 w-3 shrink-0" />
              <span className="truncate">{col.name}</span>
              <span className="ml-auto shrink-0 text-[10px]">{col.data_type}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export { type Datasource }
