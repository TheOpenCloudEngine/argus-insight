"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Zap, Trash2, FileText, Layers } from "lucide-react";
import Link from "next/link";
import {
  fetchCollection,
  fetchDocuments,
  fetchEmbeddingStats,
  fetchSources,
  fetchJobs,
  embedCollection,
  clearEmbeddings,
  type Collection,
  type Document,
  type EmbeddingStats,
  type DataSource,
  type SyncJob,
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
    try {
      toast.info("Embedding started...");
      const result = await embedCollection(id);
      toast.success(`Embedded ${result.processed}/${result.total} chunks (${result.duration_ms}ms)`);
      fetchEmbeddingStats(id).then(setEmbStats);
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const handleClear = async () => {
    if (!confirm("Clear all embeddings? You'll need to re-embed afterwards.")) return;
    try {
      const result = await clearEmbeddings(id);
      toast.success(`Cleared ${result.cleared} embeddings`);
      fetchEmbeddingStats(id).then(setEmbStats);
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  if (!collection) return <div className="text-gray-500">Loading...</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/collections" className="text-gray-500 hover:text-gray-700">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{collection.name}</h1>
          <p className="text-sm text-gray-500">{collection.description || "No description"}</p>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <MiniStat icon={<FileText className="h-4 w-4" />} label="Documents" value={collection.document_count} />
        <MiniStat icon={<Layers className="h-4 w-4" />} label="Chunks" value={collection.chunk_count} />
        <MiniStat
          icon={<Zap className="h-4 w-4" />}
          label="Embedded"
          value={embStats ? `${embStats.coverage_pct}%` : "-"}
        />
        <MiniStat label="Model" value={collection.embedding_model} />
        <MiniStat label="Strategy" value={`${collection.chunk_strategy} (${collection.chunk_max_size})`} />
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button onClick={handleEmbed} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm flex items-center gap-1">
          <Zap className="h-3 w-3" /> Generate Embeddings
        </button>
        <button onClick={handleClear} className="px-3 py-1.5 border rounded text-sm flex items-center gap-1 text-red-600">
          <Trash2 className="h-3 w-3" /> Clear Embeddings
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b flex gap-4">
        {(["documents", "sources", "jobs"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`py-2 text-sm capitalize ${tab === t ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-500"}`}
          >
            {t} {t === "documents" ? `(${docTotal})` : t === "sources" ? `(${sources.length})` : `(${jobs.length})`}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "documents" && (
        <table className="w-full text-sm">
          <thead className="text-gray-500 border-b">
            <tr>
              <th className="text-left py-2">External ID</th>
              <th className="text-left py-2">Title</th>
              <th className="text-right py-2">Chunks</th>
              <th className="text-left py-2">Embedded</th>
              <th className="text-left py-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id} className="border-b">
                <td className="py-2 font-mono text-xs">{d.external_id}</td>
                <td className="py-2">{d.title || "-"}</td>
                <td className="py-2 text-right">{d.chunk_count}</td>
                <td className="py-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${d.is_embedded === "true" ? "bg-green-100 text-green-700" : "bg-gray-100"}`}>
                    {d.is_embedded}
                  </span>
                </td>
                <td className="py-2 text-xs text-gray-500">{new Date(d.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "sources" && (
        <table className="w-full text-sm">
          <thead className="text-gray-500 border-b">
            <tr>
              <th className="text-left py-2">Name</th>
              <th className="text-left py-2">Type</th>
              <th className="text-left py-2">Sync Mode</th>
              <th className="text-left py-2">Last Sync</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id} className="border-b">
                <td className="py-2 font-medium">{s.name}</td>
                <td className="py-2">{s.source_type}</td>
                <td className="py-2">{s.sync_mode}</td>
                <td className="py-2 text-xs text-gray-500">{s.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "Never"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "jobs" && (
        <table className="w-full text-sm">
          <thead className="text-gray-500 border-b">
            <tr>
              <th className="text-left py-2">ID</th>
              <th className="text-left py-2">Type</th>
              <th className="text-left py-2">Status</th>
              <th className="text-right py-2">Processed</th>
              <th className="text-left py-2">Started</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className="border-b">
                <td className="py-2">{j.id}</td>
                <td className="py-2">{j.job_type}</td>
                <td className="py-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${j.status === "completed" ? "bg-green-100 text-green-700" : j.status === "failed" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>
                    {j.status}
                  </span>
                </td>
                <td className="py-2 text-right">{j.processed_items}/{j.total_items}</td>
                <td className="py-2 text-xs text-gray-500">{new Date(j.started_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function MiniStat({ icon, label, value }: { icon?: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded p-3">
      <div className="flex items-center gap-1 text-xs text-gray-500 mb-1">{icon}{label}</div>
      <div className="font-semibold text-sm truncate">{value}</div>
    </div>
  );
}
