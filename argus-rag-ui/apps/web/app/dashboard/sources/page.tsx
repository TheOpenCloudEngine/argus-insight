"use client";

import { useEffect, useState } from "react";
import {
  fetchCollections, fetchSources, triggerSync, createSource, queryPreview,
  type Collection, type DataSource, type QueryPreviewResult,
} from "@/lib/api";
import { Play, Plus, Database, X, Search, Check } from "lucide-react";
import { toast } from "sonner";

const DB_TYPES = [
  { value: "mysql", label: "MySQL", port: 3306 },
  { value: "postgresql", label: "PostgreSQL", port: 5432 },
  { value: "oracle", label: "Oracle", port: 1521 },
  { value: "mssql", label: "SQL Server", port: 1433 },
];

export default function SourcesPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [sourceMap, setSourceMap] = useState<Record<number, DataSource[]>>({});
  const [showWizard, setShowWizard] = useState(false);

  const loadAll = async () => {
    const colls = await fetchCollections();
    setCollections(colls);
    const map: Record<number, DataSource[]> = {};
    for (const c of colls) {
      try { map[c.id] = await fetchSources(c.id); } catch { map[c.id] = []; }
    }
    setSourceMap(map);
  };

  useEffect(() => { loadAll(); }, []);

  const handleSync = async (sourceId: number) => {
    toast.info("Sync triggered...");
    try {
      const r = await triggerSync(sourceId);
      toast.success(`Processed ${r.processed}/${r.total} (${r.duration_ms}ms)`);
      loadAll();
    } catch (e: any) { toast.error(e.message); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div />
        <button
          onClick={() => setShowWizard(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] text-sm font-medium"
          style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
        >
          <Plus className="h-4 w-4" /> Add DB Query Source
        </button>
      </div>

      {showWizard && (
        <DBQueryWizard
          collections={collections}
          onClose={() => setShowWizard(false)}
          onCreated={() => { setShowWizard(false); loadAll(); }}
        />
      )}

      {collections.map((c) => (
        <div key={c.id} className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
          <div className="px-4 py-3 border-b flex items-center gap-2">
            <Database className="h-4 w-4 text-[var(--muted-foreground)]" />
            <h2 className="text-sm font-semibold">{c.name}</h2>
          </div>
          {(sourceMap[c.id] || []).length === 0 ? (
            <div className="p-4 text-sm text-[var(--muted-foreground)]">No data sources</div>
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="text-[var(--muted-foreground)] text-xs uppercase tracking-wider border-b">
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Type</th>
                <th className="text-left px-4 py-2 font-medium">Mode</th>
                <th className="text-left px-4 py-2 font-medium">Last Sync</th>
                <th className="text-right px-4 py-2 font-medium">Action</th>
              </tr></thead>
              <tbody>{(sourceMap[c.id] || []).map((s) => (
                <tr key={s.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2.5 font-medium">{s.name}</td>
                  <td className="px-4 py-2.5">
                    <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--secondary)] text-[var(--secondary-foreground)]">{s.source_type}</span>
                  </td>
                  <td className="px-4 py-2.5">{s.sync_mode}</td>
                  <td className="px-4 py-2.5 text-xs text-[var(--muted-foreground)]">{s.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "Never"}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => handleSync(s.id)} className="p-1.5 rounded-[var(--radius)] hover:bg-[var(--accent)]" style={{ color: "var(--primary)" }}>
                      <Play className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );
}

// ===========================================================================
// DB Query Wizard — Step-by-step: Connection → Query → Preview → Columns → Save
// ===========================================================================

function DBQueryWizard({
  collections,
  onClose,
  onCreated,
}: {
  collections: Collection[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [step, setStep] = useState<"connect" | "preview" | "columns">("connect");

  // Connection form
  const [collectionId, setCollectionId] = useState(collections[0]?.id || 0);
  const [sourceName, setSourceName] = useState("");
  const [dbType, setDbType] = useState("mysql");
  const [host, setHost] = useState("");
  const [port, setPort] = useState(3306);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [database, setDatabase] = useState("");
  const [query, setQuery] = useState("SELECT * FROM ");

  // Preview results
  const [preview, setPreview] = useState<QueryPreviewResult | null>(null);
  const [loading, setLoading] = useState(false);

  // Column selection
  const [idColumn, setIdColumn] = useState("");
  const [titleColumn, setTitleColumn] = useState("");
  const [textColumns, setTextColumns] = useState<string[]>([]);

  const handleDbTypeChange = (val: string) => {
    setDbType(val);
    const db = DB_TYPES.find((d) => d.value === val);
    if (db) setPort(db.port);
  };

  const handlePreview = async () => {
    if (!query.trim() || !host.trim()) {
      toast.error("Enter connection details and SQL query");
      return;
    }
    setLoading(true);
    try {
      const result = await queryPreview({
        db_type: dbType, host, port, username, password, database, query, max_rows: 10,
      });
      setPreview(result);
      // Auto-select first column as ID
      if (result.columns.length > 0) {
        setIdColumn(result.columns[0]);
        setTextColumns(result.columns);
      }
      setStep("preview");
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  };

  const toggleTextColumn = (col: string) => {
    setTextColumns((prev) =>
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
    );
  };

  const handleSave = async () => {
    if (!sourceName.trim()) { toast.error("Enter source name"); return; }
    if (!idColumn) { toast.error("Select an ID column"); return; }
    if (textColumns.length === 0) { toast.error("Select at least one text column"); return; }

    try {
      const config = JSON.stringify({
        db_type: dbType, host, port, username, password, database, query,
        id_column: idColumn,
        title_column: titleColumn || undefined,
        text_columns: textColumns,
      });

      await createSource(collectionId, {
        name: sourceName,
        source_type: "db_query",
        config_json: config,
        sync_mode: "manual",
      });
      toast.success("Data source created! Click Sync to import data.");
      onCreated();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const inputCls = "w-full rounded-[var(--radius)] border bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]";
  const labelCls = "text-xs font-medium text-[var(--muted-foreground)] mb-1 block";

  return (
    <div className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
      {/* Header */}
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <h3 className="text-sm font-semibold">Add DB Query Source</h3>
        <button onClick={onClose} className="p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Step indicators */}
      <div className="px-4 py-2 border-b flex gap-4 text-xs">
        {[
          { key: "connect", label: "1. Connection & Query" },
          { key: "preview", label: "2. Preview Data" },
          { key: "columns", label: "3. Select Columns" },
        ].map((s) => (
          <span key={s.key} className={`font-medium ${step === s.key ? "text-[var(--foreground)]" : "text-[var(--muted-foreground)]"}`}>
            {s.label}
          </span>
        ))}
      </div>

      <div className="p-4">
        {/* Step 1: Connection + Query */}
        {step === "connect" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Collection</label>
                <select value={collectionId} onChange={(e) => setCollectionId(Number(e.target.value))} className={inputCls}>
                  {collections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls}>Source Name</label>
                <input value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="e.g., sakila.film table" className={inputCls} />
              </div>
            </div>

            <div className="grid grid-cols-4 gap-3">
              <div>
                <label className={labelCls}>DB Type</label>
                <select value={dbType} onChange={(e) => handleDbTypeChange(e.target.value)} className={inputCls}>
                  {DB_TYPES.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls}>Host</label>
                <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="localhost" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Port</label>
                <input type="number" value={port} onChange={(e) => setPort(Number(e.target.value))} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Database</label>
                <input value={database} onChange={(e) => setDatabase(e.target.value)} placeholder="sakila" className={inputCls} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Username</label>
                <input value={username} onChange={(e) => setUsername(e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} />
              </div>
            </div>

            <div>
              <label className={labelCls}>SQL Query</label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={4}
                className={`${inputCls} font-mono text-xs`}
                placeholder="SELECT id, name, description FROM my_table"
              />
            </div>

            <button
              onClick={handlePreview}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-[var(--radius)] text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
            >
              <Search className="h-4 w-4" />
              {loading ? "Querying..." : "Preview Query"}
            </button>
          </div>
        )}

        {/* Step 2: Preview Data */}
        {step === "preview" && preview && (
          <div className="space-y-4">
            <div className="text-sm text-[var(--muted-foreground)]">
              {preview.total_rows} rows returned from <strong>{preview.db_type}://{preview.database}</strong>
              {" · "}{preview.columns.length} columns
            </div>

            <div className="overflow-x-auto rounded-[var(--radius)] border">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-[var(--muted)]">
                    {preview.columns.map((col) => (
                      <th key={col} className="text-left px-3 py-2 font-semibold whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, i) => (
                    <tr key={i} className="border-t border-[var(--border)]">
                      {preview.columns.map((col) => (
                        <td key={col} className="px-3 py-1.5 whitespace-nowrap max-w-48 truncate">
                          {row[col] != null ? String(row[col]) : <span className="text-[var(--muted-foreground)]">NULL</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex gap-2">
              <button onClick={() => setStep("connect")} className="px-3 py-1.5 rounded-[var(--radius)] border text-sm">Back</button>
              <button
                onClick={() => setStep("columns")}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-[var(--radius)] text-sm font-medium"
                style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
              >
                Next: Select Columns
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Column Selection */}
        {step === "columns" && preview && (
          <div className="space-y-4">
            <p className="text-sm text-[var(--muted-foreground)]">
              Choose which columns to use for identification, title, and embedding text.
            </p>

            <div className="overflow-x-auto rounded-[var(--radius)] border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-[var(--muted)] text-xs uppercase tracking-wider">
                    <th className="text-left px-4 py-2.5 font-medium">Column</th>
                    <th className="text-center px-4 py-2.5 font-medium">Sample Value</th>
                    <th className="text-center px-4 py-2.5 font-medium w-24">ID</th>
                    <th className="text-center px-4 py-2.5 font-medium w-24">Title</th>
                    <th className="text-center px-4 py-2.5 font-medium w-24">Embed</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.columns.map((col) => {
                    const sampleVal = preview.rows[0]?.[col];
                    return (
                      <tr key={col} className="border-t border-[var(--border)]">
                        <td className="px-4 py-2.5 font-mono text-xs font-semibold">{col}</td>
                        <td className="px-4 py-2.5 text-xs text-[var(--muted-foreground)] max-w-48 truncate">
                          {sampleVal != null ? String(sampleVal).substring(0, 80) : "NULL"}
                        </td>
                        <td className="text-center px-4 py-2.5">
                          <input
                            type="radio"
                            name="id_column"
                            checked={idColumn === col}
                            onChange={() => setIdColumn(col)}
                            className="accent-[oklch(0.488_0.243_264.376)]"
                          />
                        </td>
                        <td className="text-center px-4 py-2.5">
                          <input
                            type="radio"
                            name="title_column"
                            checked={titleColumn === col}
                            onChange={() => setTitleColumn(col)}
                            className="accent-[oklch(0.488_0.243_264.376)]"
                          />
                        </td>
                        <td className="text-center px-4 py-2.5">
                          <input
                            type="checkbox"
                            checked={textColumns.includes(col)}
                            onChange={() => toggleTextColumn(col)}
                            className="accent-[oklch(0.488_0.243_264.376)]"
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Legend */}
            <div className="flex gap-6 text-xs text-[var(--muted-foreground)]">
              <span><strong>ID</strong> — external_id로 사용할 고유 컬럼 (필수)</span>
              <span><strong>Title</strong> — 문서 제목 컬럼 (선택)</span>
              <span><strong>Embed</strong> — 임베딩할 텍스트 컬럼들 (체크된 컬럼을 연결하여 임베딩)</span>
            </div>

            {/* Summary */}
            <div className="rounded-[var(--radius)] bg-[var(--muted)] p-3 text-xs space-y-1">
              <div><strong>ID Column:</strong> {idColumn || "(not selected)"}</div>
              <div><strong>Title Column:</strong> {titleColumn || "(none)"}</div>
              <div><strong>Text Columns:</strong> {textColumns.length > 0 ? textColumns.join(", ") : "(none selected)"}</div>
              <div><strong>Embedding Text:</strong> {textColumns.map((c) => `{${c}}`).join(" | ") || "-"}</div>
            </div>

            <div className="flex gap-2">
              <button onClick={() => setStep("preview")} className="px-3 py-1.5 rounded-[var(--radius)] border text-sm">Back</button>
              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-[var(--radius)] text-sm font-medium"
                style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
              >
                <Check className="h-4 w-4" /> Save Data Source
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
