"use client";

import { useEffect, useState } from "react";
import { fetchCollections, fetchSources, triggerSync, type Collection, type DataSource } from "@/lib/api";
import { Play } from "lucide-react";
import { toast } from "sonner";

export default function SourcesPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [sourceMap, setSourceMap] = useState<Record<number, DataSource[]>>({});

  useEffect(() => {
    fetchCollections().then(async (colls) => {
      setCollections(colls);
      const map: Record<number, DataSource[]> = {};
      for (const c of colls) { try { map[c.id] = await fetchSources(c.id); } catch { map[c.id] = []; } }
      setSourceMap(map);
    });
  }, []);

  const handleSync = async (sourceId: number) => {
    toast.info("Sync triggered...");
    try {
      const r = await triggerSync(sourceId);
      toast.success(`Processed ${r.processed}/${r.total} (${r.duration_ms}ms)`);
    } catch (e: any) { toast.error(e.message); }
  };

  return (
    <div className="space-y-4">
      {collections.map((c) => (
        <div key={c.id} className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
          <div className="px-4 py-3 border-b">
            <h2 className="text-sm font-semibold">{c.name}</h2>
          </div>
          {(sourceMap[c.id] || []).length === 0 ? (
            <div className="p-4 text-sm text-[var(--muted-foreground)]">No data sources configured</div>
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
                  <td className="px-4 py-2.5"><span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--secondary)] text-[var(--secondary-foreground)]">{s.source_type}</span></td>
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
