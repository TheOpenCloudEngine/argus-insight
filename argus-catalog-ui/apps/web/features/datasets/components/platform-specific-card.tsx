"use client"

import { useMemo, useState } from "react"
import { ChevronRight, Settings2 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { AgGridReact } from "ag-grid-react"
import { AllCommunityModule, ModuleRegistry, type ColDef } from "ag-grid-community"
import dynamic from "next/dynamic"

ModuleRegistry.registerModules([AllCommunityModule])
const MonacoEditor = dynamic(() => import("@monaco-editor/react").then(m => m.default), { ssr: false })

// ---------------------------------------------------------------------------
// Collapsible section
// ---------------------------------------------------------------------------

function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="mt-3">
      <button
        type="button"
        className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        onClick={() => setOpen(!open)}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`}
        />
        {title}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const units = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

function formatNumber(n: number): string {
  return n.toLocaleString()
}

// ---------------------------------------------------------------------------
// Table-level property renderers
// ---------------------------------------------------------------------------

type PropItem = { label: string; value: string }

function mysqlTableProps(table: Record<string, unknown>): PropItem[] {
  const items: PropItem[] = []
  if (table.engine) items.push({ label: "Engine", value: String(table.engine) })
  if (table.row_format) items.push({ label: "Row Format", value: String(table.row_format) })
  if (table.collation) items.push({ label: "Collation", value: String(table.collation) })
  if (table.estimated_rows != null)
    items.push({ label: "Estimated Rows", value: formatNumber(Number(table.estimated_rows)) })
  if (table.data_size != null)
    items.push({ label: "Data Size", value: formatBytes(Number(table.data_size)) })
  if (table.index_size != null)
    items.push({ label: "Index Size", value: formatBytes(Number(table.index_size)) })
  if (table.avg_row_length != null)
    items.push({ label: "Avg Row Length", value: `${formatNumber(Number(table.avg_row_length))} B` })
  if (table.auto_increment != null)
    items.push({ label: "Auto Increment", value: formatNumber(Number(table.auto_increment)) })
  if (table.create_time) items.push({ label: "Created", value: String(table.create_time) })
  if (table.update_time) items.push({ label: "Updated", value: String(table.update_time) })
  if (table.create_options) items.push({ label: "Options", value: String(table.create_options) })
  return items
}

function pgTableProps(table: Record<string, unknown>): PropItem[] {
  const items: PropItem[] = []
  if (table.owner) items.push({ label: "Owner", value: String(table.owner) })
  if (table.kind) items.push({ label: "Kind", value: String(table.kind) })
  if (table.persistence) items.push({ label: "Persistence", value: String(table.persistence) })
  if (table.estimated_rows != null)
    items.push({ label: "Estimated Rows", value: formatNumber(Number(table.estimated_rows)) })
  if (table.total_size != null)
    items.push({ label: "Total Size", value: formatBytes(Number(table.total_size)) })
  if (table.table_size != null)
    items.push({ label: "Table Size", value: formatBytes(Number(table.table_size)) })
  if (table.index_size != null)
    items.push({ label: "Index Size", value: formatBytes(Number(table.index_size)) })
  if (table.has_indexes != null)
    items.push({ label: "Has Indexes", value: table.has_indexes ? "Yes" : "No" })
  if (table.has_triggers != null)
    items.push({ label: "Has Triggers", value: table.has_triggers ? "Yes" : "No" })
  return items
}

// ---------------------------------------------------------------------------
// COLUMNS (AG Grid)
// ---------------------------------------------------------------------------

function ColumnsGrid({
  platformType,
  columns,
}: {
  platformType: string
  columns: Record<string, Record<string, unknown>>
}) {
  const entries = Object.entries(columns)
  if (entries.length === 0) return null

  const isMySQL = platformType === "mysql"

  const columnDefs = useMemo<ColDef[]>(() => {
    const defs: ColDef[] = [
      { headerName: "Column", field: "column", pinned: "left", minWidth: 120, sortable: true, filter: true },
    ]
    if (isMySQL) {
      defs.push(
        { headerName: "Key", field: "key", width: 70, sortable: true },
        { headerName: "Default", field: "default", minWidth: 120 },
        { headerName: "Extra", field: "extra", minWidth: 120 },
        { headerName: "Charset", field: "charset", width: 100 },
        { headerName: "Collation", field: "collation", minWidth: 140 },
      )
    } else {
      defs.push(
        { headerName: "Default", field: "default", minWidth: 150 },
        { headerName: "Constraints", field: "constraints", minWidth: 200 },
      )
    }
    return defs
  }, [isMySQL])

  const rowData = useMemo(() =>
    entries.map(([colName, props]) => {
      if (isMySQL) {
        return {
          column: colName,
          key: String(props.key ?? ""),
          default: String(props.default ?? ""),
          extra: String(props.extra ?? ""),
          charset: String(props.charset ?? ""),
          collation: String(props.collation ?? ""),
        }
      }
      const constraints = Array.isArray(props.constraints)
        ? (props.constraints as { type: string; references?: string }[])
            .map(c => c.references ? `${c.type} → ${c.references}` : c.type)
            .join(", ")
        : ""
      return {
        column: colName,
        default: String(props.default ?? ""),
        constraints,
      }
    }),
    [entries, isMySQL],
  )

  return (
    <CollapsibleSection title={`COLUMNS (${entries.length})`}>
      <div
        className="border rounded ag-theme-alpine"
        style={{
          height: Math.min(entries.length * 32 + 40, 300),
          "--ag-font-family": "var(--font-d2coding), 'D2Coding', Consolas, monospace",
          "--ag-font-size": "12px",
        } as React.CSSProperties}
      >
        <AgGridReact
          columnDefs={columnDefs}
          rowData={rowData}
          defaultColDef={{ resizable: true, sortable: false, filter: false, minWidth: 60 }}
          headerHeight={30}
          rowHeight={26}
          suppressCellFocus
          rowSelection={{ mode: "singleRow", enableClickSelection: false }}
          animateRows={false}
        />
      </div>
    </CollapsibleSection>
  )
}

// ---------------------------------------------------------------------------
// INDEXES (AG Grid)
// ---------------------------------------------------------------------------

function IndexesGrid({ indexes }: { indexes: { name: string; definition: string }[] }) {
  if (!indexes || indexes.length === 0) return null

  const columnDefs = useMemo<ColDef[]>(() => [
    { headerName: "Name", field: "name", minWidth: 150, sortable: true, filter: true },
    { headerName: "Definition", field: "definition", minWidth: 300, flex: 1 },
  ], [])

  return (
    <CollapsibleSection title={`INDEXES (${indexes.length})`}>
      <div
        className="border rounded ag-theme-alpine"
        style={{
          height: Math.min(indexes.length * 32 + 40, 250),
          "--ag-font-family": "var(--font-d2coding), 'D2Coding', Consolas, monospace",
          "--ag-font-size": "12px",
        } as React.CSSProperties}
      >
        <AgGridReact
          columnDefs={columnDefs}
          rowData={indexes}
          defaultColDef={{ resizable: true, sortable: false, filter: false, minWidth: 60 }}
          headerHeight={30}
          rowHeight={26}
          suppressCellFocus
          rowSelection={{ mode: "singleRow", enableClickSelection: false }}
          animateRows={false}
        />
      </div>
    </CollapsibleSection>
  )
}

// ---------------------------------------------------------------------------
// DDL (Monaco Editor, SQL syntax highlight)
// ---------------------------------------------------------------------------

function DDLViewer({ ddl }: { ddl: string }) {
  const lineCount = useMemo(() => ddl.split("\n").length, [ddl])

  return (
    <CollapsibleSection title="CREATE TABLE DDL">
      <div className="border rounded overflow-hidden">
        <MonacoEditor
          height={Math.min(lineCount * 20 + 20, 400)}
          language="sql"
          value={ddl}
          theme="vs"
          options={{
            readOnly: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 13,
            fontFamily: "var(--font-d2coding), 'D2Coding', Consolas, 'Courier New', monospace",
            lineNumbers: "on",
            renderLineHighlight: "none",
            overviewRulerLanes: 0,
            hideCursorInOverviewRuler: true,
            wordWrap: "off",
            domReadOnly: true,
            padding: { top: 8, bottom: 8 },
          }}
        />
      </div>
    </CollapsibleSection>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type PlatformSpecificCardProps = {
  platformType: string
  properties: Record<string, unknown>
}

export function PlatformSpecificCard({ platformType, properties }: PlatformSpecificCardProps) {
  const table = (properties.table ?? {}) as Record<string, unknown>
  const columns = (properties.columns ?? {}) as Record<string, Record<string, unknown>>
  const indexes = (properties.indexes ?? []) as { name: string; definition: string }[]
  const ddl = (properties.ddl ?? "") as string

  const isMySQL = platformType === "mysql"
  const tableProps = isMySQL ? mysqlTableProps(table) : pgTableProps(table)

  if (tableProps.length === 0 && Object.keys(columns).length === 0 && indexes.length === 0 && !ddl) {
    return null
  }

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Settings2 className="h-4 w-4" />
          Platform Specific
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Table-level properties */}
        {tableProps.length > 0 && (
          <div className="grid gap-x-6 gap-y-2 grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 text-sm">
            {tableProps.map((p) => (
              <div key={p.label}>
                <span className="text-xs text-muted-foreground">{p.label}</span>
                <p className="font-medium font-[family-name:var(--font-d2coding)] text-sm">{p.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* COLUMNS (AG Grid, collapsed) */}
        <ColumnsGrid platformType={platformType} columns={columns} />

        {/* INDEXES (AG Grid, collapsed) — PostgreSQL only */}
        {!isMySQL && <IndexesGrid indexes={indexes} />}

        {/* CREATE TABLE DDL (Monaco Editor, collapsed) */}
        {ddl && <DDLViewer ddl={ddl} />}
      </CardContent>
    </Card>
  )
}
