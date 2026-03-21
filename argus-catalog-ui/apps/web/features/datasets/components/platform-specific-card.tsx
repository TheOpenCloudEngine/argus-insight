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

function hiveImpalaTableProps(table: Record<string, unknown>): PropItem[] {
  const items: PropItem[] = []
  if (table.table_type) items.push({ label: "Table Type", value: String(table.table_type) })
  if (table.location) items.push({ label: "Location", value: String(table.location) })
  if (table.storage_format) items.push({ label: "Storage Format", value: String(table.storage_format) })
  if (table.compression) items.push({ label: "Compression", value: String(table.compression) })
  if (table.serde) items.push({ label: "SerDe", value: String(table.serde) })
  if (table.input_format) items.push({ label: "Input Format", value: String(table.input_format) })
  if (table.output_format) items.push({ label: "Output Format", value: String(table.output_format) })
  if (table.field_delimiter) items.push({ label: "Field Delimiter", value: String(table.field_delimiter) })
  if (table.line_delimiter) items.push({ label: "Line Delimiter", value: String(table.line_delimiter) })
  if (table.collection_delimiter)
    items.push({ label: "Collection Delimiter", value: String(table.collection_delimiter) })
  if (table.map_key_delimiter) items.push({ label: "Map Key Delimiter", value: String(table.map_key_delimiter) })
  if (table.partition_keys) items.push({ label: "Partition Keys", value: String(table.partition_keys) })
  if (table.bucket_columns) items.push({ label: "Bucket Columns", value: String(table.bucket_columns) })
  if (table.bucket_count != null)
    items.push({ label: "Bucket Count", value: formatNumber(Number(table.bucket_count)) })
  if (table.sort_columns) items.push({ label: "Sort Columns", value: String(table.sort_columns) })
  if (table.transactional != null)
    items.push({ label: "Transactional", value: table.transactional ? "Yes" : "No" })
  if (table.table_format) items.push({ label: "Table Format", value: String(table.table_format) })
  if (table.kudu_master_hosts) items.push({ label: "Kudu Masters", value: String(table.kudu_master_hosts) })
  if (table.estimated_rows != null)
    items.push({ label: "Estimated Rows", value: formatNumber(Number(table.estimated_rows)) })
  if (table.total_size != null)
    items.push({ label: "Total Size", value: formatBytes(Number(table.total_size)) })
  if (table.num_files != null)
    items.push({ label: "Number of Files", value: formatNumber(Number(table.num_files)) })
  if (table.owner) items.push({ label: "Owner", value: String(table.owner) })
  if (table.created_at) items.push({ label: "Created", value: String(table.created_at) })
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

function TblPropertiesGrid({ tblProperties }: { tblProperties: Record<string, string> }) {
  const entries = Object.entries(tblProperties)
  if (entries.length === 0) return null

  const columnDefs = useMemo<ColDef[]>(() => [
    { headerName: "Key", field: "key", minWidth: 200, sortable: true, filter: true },
    { headerName: "Value", field: "value", minWidth: 300, flex: 1 },
  ], [])

  const rowData = useMemo(() =>
    entries.map(([key, value]) => ({ key, value: String(value) })),
    [entries],
  )

  return (
    <CollapsibleSection title={`TABLE PROPERTIES (${entries.length})`}>
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

export function PlatformSpecificCard({ platformType, properties }: PlatformSpecificCardProps) {
  const table = (properties.table ?? {}) as Record<string, unknown>
  const columns = (properties.columns ?? {}) as Record<string, Record<string, unknown>>
  const indexes = (properties.indexes ?? []) as { name: string; definition: string }[]
  const ddl = (properties.ddl ?? "") as string
  const tblProperties = (properties.tbl_properties ?? {}) as Record<string, string>

  const isMySQL = platformType === "mysql"
  const isHiveImpala = platformType === "hive" || platformType === "impala"

  const tableProps = isHiveImpala
    ? hiveImpalaTableProps(table)
    : isMySQL ? mysqlTableProps(table) : pgTableProps(table)

  const hasContent =
    tableProps.length > 0 ||
    Object.keys(columns).length > 0 ||
    indexes.length > 0 ||
    Object.keys(tblProperties).length > 0 ||
    !!ddl

  if (!hasContent) {
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
                <p className="font-medium font-[family-name:var(--font-d2coding)] text-sm break-all">{p.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* COLUMNS (AG Grid, collapsed) — MySQL/PostgreSQL */}
        {!isHiveImpala && <ColumnsGrid platformType={platformType} columns={columns} />}

        {/* INDEXES (AG Grid, collapsed) — PostgreSQL only */}
        {!isMySQL && !isHiveImpala && <IndexesGrid indexes={indexes} />}

        {/* TABLE PROPERTIES (AG Grid, collapsed) — Hive/Impala */}
        {isHiveImpala && <TblPropertiesGrid tblProperties={tblProperties} />}

        {/* CREATE TABLE DDL (Monaco Editor, collapsed) */}
        {ddl && <DDLViewer ddl={ddl} />}
      </CardContent>
    </Card>
  )
}
