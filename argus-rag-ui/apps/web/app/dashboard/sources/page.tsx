"use client";

import { useEffect, useState } from "react";
import {
  fetchCollections, fetchSources, triggerSync, createSource,
  queryPreview, urlPreview,
  type Collection, type DataSource, type QueryPreviewResult,
} from "@/lib/api";
import {
  Play, Plus, Database, X, Search, Check, Globe, Link2, Server,
} from "lucide-react";
import { toast } from "sonner";

const SOURCE_TYPES = [
  { value: "catalog_api", label: "Catalog API", icon: Server, desc: "argus-catalog-server에서 메타데이터 수집" },
  { value: "db_query", label: "DB Query", icon: Database, desc: "SQL 쿼리로 DB 테이블 데이터 수집" },
  { value: "http", label: "HTTP URL", icon: Globe, desc: "REST API 또는 웹 URL에서 데이터 수집" },
];

const DB_TYPES = [
  { value: "mysql", label: "MySQL", port: 3306 },
  { value: "postgresql", label: "PostgreSQL", port: 5432 },
  { value: "oracle", label: "Oracle", port: 1521 },
  { value: "mssql", label: "SQL Server (MSSQL)", port: 1433 },
];

const CATALOG_ENTITIES = [
  { value: "datasets", label: "Datasets" },
  { value: "models", label: "ML Models" },
  { value: "glossary", label: "Glossary Terms" },
  { value: "standards", label: "Standard Terms" },
];

export default function SourcesPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [sourceMap, setSourceMap] = useState<Record<number, DataSource[]>>({});
  const [wizardType, setWizardType] = useState<string | null>(null);

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
      {/* Action buttons */}
      <div className="flex items-center gap-2 justify-end">
        {SOURCE_TYPES.map((st) => {
          const Icon = st.icon;
          return (
            <button key={st.value} onClick={() => setWizardType(st.value)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] border text-sm font-medium hover:bg-[var(--accent)]">
              <Icon className="h-3.5 w-3.5" /> {st.label}
            </button>
          );
        })}
      </div>

      {/* Wizards */}
      {wizardType === "catalog_api" && (
        <CatalogAPIWizard collections={collections}
          onClose={() => setWizardType(null)} onCreated={() => { setWizardType(null); loadAll(); }} />
      )}
      {wizardType === "db_query" && (
        <DBQueryWizard collections={collections}
          onClose={() => setWizardType(null)} onCreated={() => { setWizardType(null); loadAll(); }} />
      )}
      {wizardType === "http" && (
        <HTTPWizard collections={collections}
          onClose={() => setWizardType(null)} onCreated={() => { setWizardType(null); loadAll(); }} />
      )}

      {/* Source list by collection */}
      {collections.map((c) => (
        <div key={c.id} className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
          <div className="px-4 py-3 border-b flex items-center gap-2">
            <Database className="h-4 w-4 text-[var(--muted-foreground)]" />
            <h2 className="text-sm font-semibold">{c.name}</h2>
            <span className="text-xs text-[var(--muted-foreground)]">({c.document_count} docs)</span>
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
                  <td className="px-4 py-2.5"><SourceTypeBadge type={s.source_type} /></td>
                  <td className="px-4 py-2.5">{s.sync_mode}</td>
                  <td className="px-4 py-2.5 text-xs text-[var(--muted-foreground)]">{s.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "Never"}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => handleSync(s.id)} className="p-1.5 rounded-[var(--radius)] hover:bg-[var(--accent)]" style={{ color: "var(--primary)" }} title="Sync now">
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

function SourceTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    catalog_api: "bg-blue-50 text-blue-700 border-blue-200",
    db_query: "bg-emerald-50 text-emerald-700 border-emerald-200",
    http: "bg-violet-50 text-violet-700 border-violet-200",
  };
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${colors[type] || "bg-gray-50 text-gray-600 border-gray-200"}`}>
      {type}
    </span>
  );
}

// ===========================================================================
// Shared UI helpers
// ===========================================================================

const inputCls = "w-full rounded-[var(--radius)] border bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]";
const labelCls = "text-xs font-medium text-[var(--muted-foreground)] mb-1 block";

function WizardShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <h3 className="text-sm font-semibold">{title}</h3>
        <button onClick={onClose} className="p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><X className="h-4 w-4" /></button>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function PrimaryBtn({ onClick, disabled, children }: { onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="flex items-center gap-1.5 px-4 py-1.5 rounded-[var(--radius)] text-sm font-medium disabled:opacity-50"
      style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}>
      {children}
    </button>
  );
}

function PreviewTable({ preview }: { preview: QueryPreviewResult }) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius)] border">
      <table className="w-full text-xs">
        <thead><tr className="bg-[var(--muted)]">
          {preview.columns.map((col) => (
            <th key={col} className="text-left px-3 py-2 font-semibold whitespace-nowrap">{col}</th>
          ))}
        </tr></thead>
        <tbody>{preview.rows.map((row, i) => (
          <tr key={i} className="border-t border-[var(--border)]">
            {preview.columns.map((col) => (
              <td key={col} className="px-3 py-1.5 whitespace-nowrap max-w-48 truncate">
                {row[col] != null ? String(row[col]) : <span className="text-[var(--muted-foreground)]">NULL</span>}
              </td>
            ))}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function ColumnSelector({ preview, idColumn, setIdColumn, titleColumn, setTitleColumn, textColumns, toggleTextColumn }: {
  preview: QueryPreviewResult; idColumn: string; setIdColumn: (v: string) => void;
  titleColumn: string; setTitleColumn: (v: string) => void;
  textColumns: string[]; toggleTextColumn: (col: string) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-[var(--radius)] border">
        <table className="w-full text-sm">
          <thead><tr className="bg-[var(--muted)] text-xs uppercase tracking-wider">
            <th className="text-left px-4 py-2.5 font-medium">Column</th>
            <th className="text-center px-4 py-2.5 font-medium">Sample</th>
            <th className="text-center px-4 py-2.5 font-medium w-20">ID</th>
            <th className="text-center px-4 py-2.5 font-medium w-20">Title</th>
            <th className="text-center px-4 py-2.5 font-medium w-20">Embed</th>
          </tr></thead>
          <tbody>{preview.columns.map((col) => (
            <tr key={col} className="border-t border-[var(--border)]">
              <td className="px-4 py-2.5 font-mono text-xs font-semibold">{col}</td>
              <td className="px-4 py-2.5 text-xs text-[var(--muted-foreground)] max-w-48 truncate">
                {preview.rows[0]?.[col] != null ? String(preview.rows[0][col]).substring(0, 80) : "NULL"}
              </td>
              <td className="text-center"><input type="radio" name="id_col" checked={idColumn === col} onChange={() => setIdColumn(col)} /></td>
              <td className="text-center"><input type="radio" name="title_col" checked={titleColumn === col} onChange={() => setTitleColumn(col)} /></td>
              <td className="text-center"><input type="checkbox" checked={textColumns.includes(col)} onChange={() => toggleTextColumn(col)} /></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="flex gap-6 text-xs text-[var(--muted-foreground)]">
        <span><strong>ID</strong> — 고유 식별자 (필수)</span>
        <span><strong>Title</strong> — 문서 제목 (선택)</span>
        <span><strong>Embed</strong> — 임베딩할 텍스트 컬럼</span>
      </div>
      <div className="rounded-[var(--radius)] bg-[var(--muted)] p-3 text-xs space-y-1">
        <div><strong>ID:</strong> {idColumn || "(선택 안 됨)"}</div>
        <div><strong>Title:</strong> {titleColumn || "(없음)"}</div>
        <div><strong>Embed:</strong> {textColumns.length > 0 ? textColumns.map(c => `{${c}}`).join(" | ") : "(선택 안 됨)"}</div>
      </div>
    </div>
  );
}

// ===========================================================================
// 1. Catalog API Wizard
// ===========================================================================

function CatalogAPIWizard({ collections, onClose, onCreated }: { collections: Collection[]; onClose: () => void; onCreated: () => void }) {
  const [collectionId, setCollectionId] = useState(collections[0]?.id || 0);
  const [sourceName, setSourceName] = useState("");
  const [entityType, setEntityType] = useState("datasets");
  const [baseUrl, setBaseUrl] = useState("http://localhost:4600/api/v1");

  const handleSave = async () => {
    if (!sourceName.trim()) { toast.error("Enter source name"); return; }
    try {
      await createSource(collectionId, {
        name: sourceName,
        source_type: "catalog_api",
        config_json: JSON.stringify({ base_url: baseUrl, entity_type: entityType }),
        sync_mode: "manual",
      });
      toast.success("Catalog API source created");
      onCreated();
    } catch (e: any) { toast.error(e.message); }
  };

  return (
    <WizardShell title="Add Catalog API Source" onClose={onClose}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div><label className={labelCls}>Collection</label>
            <select value={collectionId} onChange={e => setCollectionId(Number(e.target.value))} className={inputCls}>
              {collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select></div>
          <div><label className={labelCls}>Source Name</label>
            <input value={sourceName} onChange={e => setSourceName(e.target.value)} placeholder="Catalog Datasets" className={inputCls} /></div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className={labelCls}>Entity Type</label>
            <select value={entityType} onChange={e => setEntityType(e.target.value)} className={inputCls}>
              {CATALOG_ENTITIES.map(e => <option key={e.value} value={e.value}>{e.label}</option>)}
            </select></div>
          <div><label className={labelCls}>Catalog API URL</label>
            <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} className={inputCls} /></div>
        </div>
        <PrimaryBtn onClick={handleSave}><Check className="h-4 w-4" /> Save</PrimaryBtn>
      </div>
    </WizardShell>
  );
}

// ===========================================================================
// 2. DB Query Wizard
// ===========================================================================

function DBQueryWizard({ collections, onClose, onCreated }: { collections: Collection[]; onClose: () => void; onCreated: () => void }) {
  const [step, setStep] = useState<"connect" | "preview" | "columns">("connect");
  const [collectionId, setCollectionId] = useState(collections[0]?.id || 0);
  const [sourceName, setSourceName] = useState("");
  const [dbType, setDbType] = useState("mysql");
  const [host, setHost] = useState("");
  const [port, setPort] = useState(3306);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [database, setDatabase] = useState("");
  const [query, setQuery] = useState("SELECT * FROM ");
  const [preview, setPreview] = useState<QueryPreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [idColumn, setIdColumn] = useState("");
  const [titleColumn, setTitleColumn] = useState("");
  const [textColumns, setTextColumns] = useState<string[]>([]);

  const handleDbTypeChange = (val: string) => { setDbType(val); const d = DB_TYPES.find(d => d.value === val); if (d) setPort(d.port); };
  const toggleTextColumn = (col: string) => setTextColumns(prev => prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]);

  const handlePreview = async () => {
    setLoading(true);
    try {
      const r = await queryPreview({ db_type: dbType, host, port, username, password, database, query, max_rows: 10 });
      setPreview(r);
      if (r.columns.length > 0) { setIdColumn(r.columns[0]); setTextColumns(r.columns); }
      setStep("preview");
    } catch (e: any) { toast.error(e.message); }
    setLoading(false);
  };

  const handleSave = async () => {
    if (!sourceName.trim()) { toast.error("Enter source name"); return; }
    if (!idColumn) { toast.error("Select ID column"); return; }
    try {
      await createSource(collectionId, {
        name: sourceName, source_type: "db_query",
        config_json: JSON.stringify({ db_type: dbType, host, port, username, password, database, query, id_column: idColumn, title_column: titleColumn || undefined, text_columns: textColumns }),
        sync_mode: "manual",
      });
      toast.success("DB Query source created");
      onCreated();
    } catch (e: any) { toast.error(e.message); }
  };

  const steps = [
    { key: "connect", label: "1. Connection & Query" },
    { key: "preview", label: "2. Preview" },
    { key: "columns", label: "3. Columns" },
  ];

  return (
    <WizardShell title="Add DB Query Source" onClose={onClose}>
      <div className="mb-4 flex gap-4 text-xs">
        {steps.map(s => <span key={s.key} className={`font-medium ${step === s.key ? "text-[var(--foreground)]" : "text-[var(--muted-foreground)]"}`}>{s.label}</span>)}
      </div>

      {step === "connect" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Collection</label>
              <select value={collectionId} onChange={e => setCollectionId(Number(e.target.value))} className={inputCls}>
                {collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select></div>
            <div><label className={labelCls}>Source Name</label>
              <input value={sourceName} onChange={e => setSourceName(e.target.value)} placeholder="sakila.film table" className={inputCls} /></div>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <div><label className={labelCls}>DB Type</label>
              <select value={dbType} onChange={e => handleDbTypeChange(e.target.value)} className={inputCls}>
                {DB_TYPES.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select></div>
            <div><label className={labelCls}>Host</label>
              <input value={host} onChange={e => setHost(e.target.value)} placeholder="localhost" className={inputCls} /></div>
            <div><label className={labelCls}>Port</label>
              <input type="number" value={port} onChange={e => setPort(Number(e.target.value))} className={inputCls} /></div>
            <div><label className={labelCls}>Database</label>
              <input value={database} onChange={e => setDatabase(e.target.value)} className={inputCls} /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Username</label><input value={username} onChange={e => setUsername(e.target.value)} className={inputCls} /></div>
            <div><label className={labelCls}>Password</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} className={inputCls} /></div>
          </div>
          <div><label className={labelCls}>SQL Query</label>
            <textarea value={query} onChange={e => setQuery(e.target.value)} rows={4} className={`${inputCls} font-mono text-xs`} placeholder="SELECT id, name, description FROM my_table" />
          </div>
          <PrimaryBtn onClick={handlePreview} disabled={loading}>
            <Search className="h-4 w-4" /> {loading ? "Querying..." : "Preview Query"}
          </PrimaryBtn>
        </div>
      )}

      {step === "preview" && preview && (
        <div className="space-y-4">
          <div className="text-sm text-[var(--muted-foreground)]">
            {preview.total_rows} rows · {preview.columns.length} columns · <strong>{preview.db_type}://{preview.database}</strong>
          </div>
          <PreviewTable preview={preview} />
          <div className="flex gap-2">
            <button onClick={() => setStep("connect")} className="px-3 py-1.5 rounded-[var(--radius)] border text-sm">Back</button>
            <PrimaryBtn onClick={() => setStep("columns")}>Next: Select Columns</PrimaryBtn>
          </div>
        </div>
      )}

      {step === "columns" && preview && (
        <div className="space-y-4">
          <ColumnSelector preview={preview} idColumn={idColumn} setIdColumn={setIdColumn} titleColumn={titleColumn} setTitleColumn={setTitleColumn} textColumns={textColumns} toggleTextColumn={toggleTextColumn} />
          <div className="flex gap-2">
            <button onClick={() => setStep("preview")} className="px-3 py-1.5 rounded-[var(--radius)] border text-sm">Back</button>
            <PrimaryBtn onClick={handleSave}><Check className="h-4 w-4" /> Save Data Source</PrimaryBtn>
          </div>
        </div>
      )}
    </WizardShell>
  );
}

// ===========================================================================
// 3. HTTP URL Wizard
// ===========================================================================

function HTTPWizard({ collections, onClose, onCreated }: { collections: Collection[]; onClose: () => void; onCreated: () => void }) {
  const [step, setStep] = useState<"connect" | "preview" | "columns">("connect");
  const [collectionId, setCollectionId] = useState(collections[0]?.id || 0);
  const [sourceName, setSourceName] = useState("");
  const [url, setUrl] = useState("https://");
  const [method, setMethod] = useState("GET");
  const [headerKey, setHeaderKey] = useState("");
  const [headerVal, setHeaderVal] = useState("");
  const [headers, setHeaders] = useState<Record<string, string>>({});
  const [responseType, setResponseType] = useState("json_array");
  const [preview, setPreview] = useState<QueryPreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [idColumn, setIdColumn] = useState("");
  const [titleColumn, setTitleColumn] = useState("");
  const [textColumns, setTextColumns] = useState<string[]>([]);

  const addHeader = () => {
    if (headerKey.trim()) { setHeaders({ ...headers, [headerKey]: headerVal }); setHeaderKey(""); setHeaderVal(""); }
  };

  const toggleTextColumn = (col: string) => setTextColumns(prev => prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]);

  const handlePreview = async () => {
    setLoading(true);
    try {
      const r = await urlPreview({ url, method, headers, response_type: responseType, max_rows: 10 });
      setPreview(r);
      if (r.columns.length > 0) { setIdColumn(r.columns[0]); setTextColumns(r.columns); }
      setStep("preview");
    } catch (e: any) { toast.error(e.message); }
    setLoading(false);
  };

  const handleSave = async () => {
    if (!sourceName.trim()) { toast.error("Enter source name"); return; }
    try {
      await createSource(collectionId, {
        name: sourceName, source_type: "http",
        config_json: JSON.stringify({
          urls: [url], method, headers: Object.keys(headers).length > 0 ? headers : undefined,
          response_type: responseType,
          id_field: idColumn || undefined, title_field: titleColumn || undefined,
          text_fields: textColumns.length > 0 ? textColumns : undefined,
        }),
        sync_mode: "manual",
      });
      toast.success("HTTP source created");
      onCreated();
    } catch (e: any) { toast.error(e.message); }
  };

  const steps = [
    { key: "connect", label: "1. URL & Settings" },
    { key: "preview", label: "2. Preview" },
    { key: "columns", label: "3. Columns" },
  ];

  return (
    <WizardShell title="Add HTTP URL Source" onClose={onClose}>
      <div className="mb-4 flex gap-4 text-xs">
        {steps.map(s => <span key={s.key} className={`font-medium ${step === s.key ? "text-[var(--foreground)]" : "text-[var(--muted-foreground)]"}`}>{s.label}</span>)}
      </div>

      {step === "connect" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Collection</label>
              <select value={collectionId} onChange={e => setCollectionId(Number(e.target.value))} className={inputCls}>
                {collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select></div>
            <div><label className={labelCls}>Source Name</label>
              <input value={sourceName} onChange={e => setSourceName(e.target.value)} placeholder="External API" className={inputCls} /></div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2"><label className={labelCls}>URL</label>
              <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://api.example.com/data" className={inputCls} /></div>
            <div><label className={labelCls}>Method</label>
              <select value={method} onChange={e => setMethod(e.target.value)} className={inputCls}>
                <option value="GET">GET</option><option value="POST">POST</option>
              </select></div>
          </div>
          <div><label className={labelCls}>Response Type</label>
            <select value={responseType} onChange={e => setResponseType(e.target.value)} className={inputCls}>
              <option value="json_array">JSON Array (배열 또는 {"{items: [...]}"} 형식)</option>
              <option value="json_object">JSON Object (단일 객체)</option>
              <option value="text">Plain Text / HTML</option>
            </select></div>
          <div><label className={labelCls}>Headers (optional)</label>
            <div className="flex gap-2">
              <input value={headerKey} onChange={e => setHeaderKey(e.target.value)} placeholder="Header name" className={`${inputCls} flex-1`} />
              <input value={headerVal} onChange={e => setHeaderVal(e.target.value)} placeholder="Value" className={`${inputCls} flex-1`} />
              <button onClick={addHeader} className="px-3 py-1.5 rounded-[var(--radius)] border text-sm">Add</button>
            </div>
            {Object.keys(headers).length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {Object.entries(headers).map(([k, v]) => (
                  <span key={k} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-[var(--muted)]">
                    {k}: {v.substring(0, 20)}{v.length > 20 ? "..." : ""}
                    <button onClick={() => { const h = { ...headers }; delete h[k]; setHeaders(h); }} className="text-[var(--muted-foreground)] hover:text-[var(--destructive)]">
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          <PrimaryBtn onClick={handlePreview} disabled={loading}>
            <Search className="h-4 w-4" /> {loading ? "Fetching..." : "Preview URL"}
          </PrimaryBtn>
        </div>
      )}

      {step === "preview" && preview && (
        <div className="space-y-4">
          <div className="text-sm text-[var(--muted-foreground)]">
            {preview.total_rows} items · {preview.columns.length} fields · <strong>{preview.url}</strong>
          </div>
          <PreviewTable preview={preview} />
          <div className="flex gap-2">
            <button onClick={() => setStep("connect")} className="px-3 py-1.5 rounded-[var(--radius)] border text-sm">Back</button>
            <PrimaryBtn onClick={() => setStep("columns")}>Next: Select Columns</PrimaryBtn>
          </div>
        </div>
      )}

      {step === "columns" && preview && (
        <div className="space-y-4">
          <ColumnSelector preview={preview} idColumn={idColumn} setIdColumn={setIdColumn} titleColumn={titleColumn} setTitleColumn={setTitleColumn} textColumns={textColumns} toggleTextColumn={toggleTextColumn} />
          <div className="flex gap-2">
            <button onClick={() => setStep("preview")} className="px-3 py-1.5 rounded-[var(--radius)] border text-sm">Back</button>
            <PrimaryBtn onClick={handleSave}><Check className="h-4 w-4" /> Save Data Source</PrimaryBtn>
          </div>
        </div>
      )}
    </WizardShell>
  );
}
