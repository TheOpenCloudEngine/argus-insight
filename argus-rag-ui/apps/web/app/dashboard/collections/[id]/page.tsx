"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Zap, Trash2, FileText, Layers } from "lucide-react";
import Link from "next/link";
import {
  fetchCollection, fetchDocuments, fetchEmbeddingStats,
  fetchSources, fetchJobs, embedCollection, clearEmbeddings,
  type Collection, type Document, type EmbeddingStats,
  type DataSource, type SyncJob,
} from "@/lib/api";
import { toast } from "sonner";

export default function CollectionDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [collection, setCollection] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [docTotal, setDocTotal] = useState(0);
  const [embStats, setEmbStats] = useState<EmbeddingStats | null>(null);
  const [sources, setSources] = useState<DataSource[]>([]);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [tab, setTab] = useState<"documents" | "sources" | "jobs">("documents");

  useEffect(() => {
    fetchCollection(id).then(setCollection);
    fetchDocuments(id).then((r) => { setDocuments(r.documents); setDocTotal(r.total); });
    fetchEmbeddingStats(id).then(setEmbStats).catch(() => {});
    fetchSources(id).then(setSources).catch(() => {});
    fetchJobs(id).then(setJobs).catch(() => {});
  }, [id]);

  const handleEmbed = async () => {
    toast.info("Embedding started...");
    try {
      const r = await embedCollection(id);
      toast.success(`Embedded ${r.processed}/${r.total} chunks (${r.duration_ms}ms)`);
      fetchEmbeddingStats(id).then(setEmbStats);
    } catch (e: any) { toast.error(e.message); }
  };

  const handleClear = async () => {
    if (!confirm("Clear all embeddings?")) return;
    try {
      const r = await clearEmbeddings(id);
      toast.success(`Cleared ${r.cleared} embeddings`);
      fetchEmbeddingStats(id).then(setEmbStats);
    } catch (e: any) { toast.error(e.message); }
  };

  if (!collection) return <div className="h-24 animate-pulse rounded-[var(--radius)] bg-[var(--muted)]" />;

  const TABS = [
    { key: "documents" as const, label: "Documents", count: docTotal },
    { key: "sources" as const, label: "Sources", count: sources.length },
    { key: "jobs" as const, label: "Jobs", count: jobs.length },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/dashboard/collections" className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h2 className="text-xl font-bold">{collection.name}</h2>
          <p className="text-sm text-[var(--muted-foreground)]">{collection.description || "No description"}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MiniStat icon={<FileText className="h-3.5 w-3.5" />} label="Documents" value={collection.document_count.toLocaleString()} />
        <MiniStat icon={<Layers className="h-3.5 w-3.5" />} label="Chunks" value={collection.chunk_count.toLocaleString()} />
        <MiniStat icon={<Zap className="h-3.5 w-3.5" />} label="Coverage" value={embStats ? `${embStats.coverage_pct}%` : "-"} />
        <MiniStat label="Model" value={collection.embedding_model.split("/").pop() || ""} />
        <MiniStat label="Strategy" value={`${collection.chunk_strategy} (${collection.chunk_max_size})`} />
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button onClick={handleEmbed} className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] text-sm font-medium" style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}>
          <Zap className="h-3.5 w-3.5" /> Generate Embeddings
        </button>
        <button onClick={handleClear} className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] border text-sm text-[var(--destructive)]">
          <Trash2 className="h-3.5 w-3.5" /> Clear Embeddings
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b flex gap-1">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${tab === t.key ? "border-b-2 text-[var(--foreground)]" : "text-[var(--muted-foreground)]"}`}
            style={tab === t.key ? { borderColor: "var(--primary)" } : {}}
          >
            {t.label} ({t.count})
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
        {tab === "documents" && <DocumentsTable documents={documents} />}
        {tab === "sources" && <SourcesTable sources={sources} />}
        {tab === "jobs" && <JobsTable jobs={jobs} />}
      </div>
    </div>
  );
}

function MiniStat({ icon, label, value }: { icon?: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="rounded-[var(--radius)] border p-3" style={{ background: "var(--card)" }}>
      <div className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] mb-1">{icon}{label}</div>
      <div className="font-semibold text-sm truncate">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s: Record<string, string> = {
    completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
    failed: "bg-red-50 text-red-700 border-red-200",
    running: "bg-amber-50 text-amber-700 border-amber-200",
    true: "bg-emerald-50 text-emerald-700 border-emerald-200",
    false: "bg-gray-50 text-gray-500 border-gray-200",
  };
  return <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${s[status] || "bg-gray-50 text-gray-500 border-gray-200"}`}>{status}</span>;
}

function DocumentsTable({ documents }: { documents: Document[] }) {
  return (
    <table className="w-full text-sm">
      <thead><tr className="text-[var(--muted-foreground)] text-xs uppercase tracking-wider border-b">
        <th className="text-left px-4 py-3 font-medium">External ID</th>
        <th className="text-left px-4 py-3 font-medium">Title</th>
        <th className="text-right px-4 py-3 font-medium">Chunks</th>
        <th className="text-left px-4 py-3 font-medium">Embedded</th>
        <th className="text-left px-4 py-3 font-medium">Created</th>
      </tr></thead>
      <tbody>{documents.map((d) => (
        <tr key={d.id} className="border-t border-[var(--border)]">
          <td className="px-4 py-2.5 font-mono text-xs">{d.external_id}</td>
          <td className="px-4 py-2.5">{d.title || "-"}</td>
          <td className="px-4 py-2.5 text-right">{d.chunk_count}</td>
          <td className="px-4 py-2.5"><StatusBadge status={d.is_embedded} /></td>
          <td className="px-4 py-2.5 text-xs text-[var(--muted-foreground)]">{new Date(d.created_at).toLocaleDateString()}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function SourcesTable({ sources }: { sources: DataSource[] }) {
  return (
    <table className="w-full text-sm">
      <thead><tr className="text-[var(--muted-foreground)] text-xs uppercase tracking-wider border-b">
        <th className="text-left px-4 py-3 font-medium">Name</th>
        <th className="text-left px-4 py-3 font-medium">Type</th>
        <th className="text-left px-4 py-3 font-medium">Sync Mode</th>
        <th className="text-left px-4 py-3 font-medium">Last Sync</th>
      </tr></thead>
      <tbody>{sources.map((s) => (
        <tr key={s.id} className="border-t border-[var(--border)]">
          <td className="px-4 py-2.5 font-medium">{s.name}</td>
          <td className="px-4 py-2.5"><span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--secondary)] text-[var(--secondary-foreground)]">{s.source_type}</span></td>
          <td className="px-4 py-2.5">{s.sync_mode}</td>
          <td className="px-4 py-2.5 text-xs text-[var(--muted-foreground)]">{s.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "Never"}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function JobsTable({ jobs }: { jobs: SyncJob[] }) {
  return (
    <table className="w-full text-sm">
      <thead><tr className="text-[var(--muted-foreground)] text-xs uppercase tracking-wider border-b">
        <th className="text-left px-4 py-3 font-medium">ID</th>
        <th className="text-left px-4 py-3 font-medium">Type</th>
        <th className="text-left px-4 py-3 font-medium">Status</th>
        <th className="text-right px-4 py-3 font-medium">Processed</th>
        <th className="text-left px-4 py-3 font-medium">Started</th>
      </tr></thead>
      <tbody>{jobs.map((j) => (
        <tr key={j.id} className="border-t border-[var(--border)]">
          <td className="px-4 py-2.5">{j.id}</td>
          <td className="px-4 py-2.5">{j.job_type}</td>
          <td className="px-4 py-2.5"><StatusBadge status={j.status} /></td>
          <td className="px-4 py-2.5 text-right">{j.processed_items}/{j.total_items}</td>
          <td className="px-4 py-2.5 text-xs text-[var(--muted-foreground)]">{new Date(j.started_at).toLocaleString()}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}
