"use client";

import { useEffect, useState } from "react";
import { Database, FileText, Layers, CheckCircle, AlertCircle } from "lucide-react";
import { fetchStats, type DashboardStats } from "@/lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats().then(setStats).catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="text-red-600">
        <AlertCircle className="inline h-5 w-5 mr-2" />
        Failed to load dashboard: {error}
      </div>
    );
  }

  if (!stats) {
    return <div className="text-gray-500">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">RAG Dashboard</h1>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          icon={<Database className="h-5 w-5 text-blue-600" />}
          label="Collections"
          value={stats.total_collections}
        />
        <StatCard
          icon={<FileText className="h-5 w-5 text-green-600" />}
          label="Documents"
          value={stats.total_documents}
        />
        <StatCard
          icon={<Layers className="h-5 w-5 text-purple-600" />}
          label="Chunks"
          value={stats.total_chunks}
        />
        <StatCard
          icon={<CheckCircle className="h-5 w-5 text-emerald-600" />}
          label="Embedded"
          value={stats.embedded_chunks}
        />
        <StatCard
          icon={<CheckCircle className="h-5 w-5 text-amber-600" />}
          label="Coverage"
          value={`${stats.coverage_pct}%`}
        />
      </div>

      {/* Embedding info */}
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-gray-500 mb-2">Embedding Model</h2>
        <p className="text-lg font-semibold">
          {stats.embedding_model || "Not configured"}
          <span className="text-sm font-normal text-gray-500 ml-2">
            ({stats.embedding_provider || "none"})
          </span>
        </p>
      </div>

      {/* Recent jobs */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Recent Jobs</h2>
        {stats.recent_jobs.length === 0 ? (
          <p className="text-gray-500 text-sm">No recent jobs</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-gray-500 border-b">
              <tr>
                <th className="text-left py-2">ID</th>
                <th className="text-left py-2">Type</th>
                <th className="text-left py-2">Status</th>
                <th className="text-right py-2">Items</th>
                <th className="text-right py-2">Started</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_jobs.map((job) => (
                <tr key={job.id} className="border-b">
                  <td className="py-2">{job.id}</td>
                  <td className="py-2">{job.job_type}</td>
                  <td className="py-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        job.status === "completed"
                          ? "bg-green-100 text-green-800"
                          : job.status === "failed"
                            ? "bg-red-100 text-red-800"
                            : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="py-2 text-right">
                    {job.processed_items}/{job.total_items}
                  </td>
                  <td className="py-2 text-right text-gray-500">
                    {new Date(job.started_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border p-4">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}
