"use client";

import { useEffect, useState } from "react";
import { fetchCollections, fetchJobs, type Collection, type SyncJob } from "@/lib/api";

export default function JobsPage() {
  const [allJobs, setAllJobs] = useState<(SyncJob & { collection_name: string })[]>([]);

  useEffect(() => {
    fetchCollections().then(async (colls) => {
      const jobs: (SyncJob & { collection_name: string })[] = [];
      for (const c of colls) {
        try { const cj = await fetchJobs(c.id, 10); for (const j of cj) jobs.push({ ...j, collection_name: c.name }); }
        catch {}
      }
      jobs.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
      setAllJobs(jobs);
    });
  }, []);

  return (
    <div className="space-y-4">
      <div className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
        <table className="w-full text-sm">
          <thead><tr className="text-[var(--muted-foreground)] text-xs uppercase tracking-wider border-b">
            <th className="text-left px-4 py-3 font-medium">ID</th>
            <th className="text-left px-4 py-3 font-medium">Collection</th>
            <th className="text-left px-4 py-3 font-medium">Type</th>
            <th className="text-left px-4 py-3 font-medium">Status</th>
            <th className="text-right px-4 py-3 font-medium">Processed</th>
            <th className="text-right px-4 py-3 font-medium">Errors</th>
            <th className="text-left px-4 py-3 font-medium">Started</th>
          </tr></thead>
          <tbody>{allJobs.map((j) => (
            <tr key={`${j.collection_id}-${j.id}`} className="border-t border-[var(--border)]">
              <td className="px-4 py-2.5">{j.id}</td>
              <td className="px-4 py-2.5 font-medium">{j.collection_name}</td>
              <td className="px-4 py-2.5">{j.job_type}</td>
              <td className="px-4 py-2.5">
                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${j.status === "completed" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : j.status === "failed" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>{j.status}</span>
              </td>
              <td className="px-4 py-2.5 text-right">{j.processed_items}/{j.total_items}</td>
              <td className="px-4 py-2.5 text-right">{j.error_items}</td>
              <td className="px-4 py-2.5 text-xs text-[var(--muted-foreground)]">{new Date(j.started_at).toLocaleString()}</td>
            </tr>
          ))}</tbody>
        </table>
        {allJobs.length === 0 && <div className="text-center py-12 text-sm text-[var(--muted-foreground)]">No jobs yet</div>}
      </div>
    </div>
  );
}
