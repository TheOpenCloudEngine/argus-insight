"use client";

import { useEffect, useState } from "react";
import { fetchCollections, fetchJobs, type Collection, type SyncJob } from "@/lib/api";

export default function JobsPage() {
  const [allJobs, setAllJobs] = useState<(SyncJob & { collection_name: string })[]>([]);

  useEffect(() => {
    fetchCollections().then(async (colls) => {
      const jobs: (SyncJob & { collection_name: string })[] = [];
      for (const c of colls) {
        try {
          const cjobs = await fetchJobs(c.id, 10);
          for (const j of cjobs) {
            jobs.push({ ...j, collection_name: c.name });
          }
        } catch {}
      }
      jobs.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
      setAllJobs(jobs);
    });
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Job History</h1>
      <table className="w-full text-sm">
        <thead className="text-gray-500 border-b">
          <tr>
            <th className="text-left py-2">ID</th>
            <th className="text-left py-2">Collection</th>
            <th className="text-left py-2">Type</th>
            <th className="text-left py-2">Status</th>
            <th className="text-right py-2">Processed</th>
            <th className="text-right py-2">Errors</th>
            <th className="text-left py-2">Started</th>
            <th className="text-left py-2">Finished</th>
          </tr>
        </thead>
        <tbody>
          {allJobs.map((j) => (
            <tr key={`${j.collection_id}-${j.id}`} className="border-b">
              <td className="py-2">{j.id}</td>
              <td className="py-2">{j.collection_name}</td>
              <td className="py-2">{j.job_type}</td>
              <td className="py-2">
                <span className={`text-xs px-1.5 py-0.5 rounded ${j.status === "completed" ? "bg-green-100 text-green-700" : j.status === "failed" ? "bg-red-100 text-red-700" : "bg-yellow-100"}`}>
                  {j.status}
                </span>
              </td>
              <td className="py-2 text-right">{j.processed_items}/{j.total_items}</td>
              <td className="py-2 text-right">{j.error_items}</td>
              <td className="py-2 text-xs text-gray-500">{new Date(j.started_at).toLocaleString()}</td>
              <td className="py-2 text-xs text-gray-500">{j.finished_at ? new Date(j.finished_at).toLocaleString() : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {allJobs.length === 0 && <p className="text-gray-500 text-center py-8">No jobs yet</p>}
    </div>
  );
}
