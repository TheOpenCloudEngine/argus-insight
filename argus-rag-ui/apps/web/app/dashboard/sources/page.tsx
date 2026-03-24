"use client";

import { useEffect, useState } from "react";
import { fetchCollections, fetchSources, triggerSync, type Collection, type DataSource } from "@/lib/api";
import { RefreshCw, Play } from "lucide-react";
import { toast } from "sonner";

export default function SourcesPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [sourcesByCollection, setSourcesByCollection] = useState<Record<number, DataSource[]>>({});

  useEffect(() => {
    fetchCollections().then(async (colls) => {
      setCollections(colls);
      const map: Record<number, DataSource[]> = {};
      for (const c of colls) {
        try {
          map[c.id] = await fetchSources(c.id);
        } catch {
          map[c.id] = [];
        }
      }
      setSourcesByCollection(map);
    });
  }, []);

  const handleSync = async (sourceId: number) => {
    try {
      toast.info("Sync triggered...");
      const result = await triggerSync(sourceId);
      toast.success(`Processed ${result.processed}/${result.total} (${result.duration_ms}ms)`);
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Data Sources</h1>
      {collections.map((c) => (
        <div key={c.id} className="border rounded-lg p-4 space-y-2">
          <h2 className="font-semibold">{c.name}</h2>
          {(sourcesByCollection[c.id] || []).length === 0 ? (
            <p className="text-sm text-gray-500">No data sources configured</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-gray-500 border-b">
                <tr>
                  <th className="text-left py-1">Name</th>
                  <th className="text-left py-1">Type</th>
                  <th className="text-left py-1">Mode</th>
                  <th className="text-left py-1">Last Sync</th>
                  <th className="text-right py-1">Action</th>
                </tr>
              </thead>
              <tbody>
                {(sourcesByCollection[c.id] || []).map((s) => (
                  <tr key={s.id} className="border-b">
                    <td className="py-1">{s.name}</td>
                    <td className="py-1">{s.source_type}</td>
                    <td className="py-1">{s.sync_mode}</td>
                    <td className="py-1 text-xs text-gray-500">
                      {s.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "Never"}
                    </td>
                    <td className="py-1 text-right">
                      <button onClick={() => handleSync(s.id)} className="p-1 text-blue-600 hover:text-blue-800">
                        <Play className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );
}
