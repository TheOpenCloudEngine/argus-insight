"use client";

import { useEffect, useState } from "react";
import {
  Database,
  FileText,
  Layers,
  CheckCircle,
  Percent,
  AlertCircle,
} from "lucide-react";
import { fetchStats, type DashboardStats } from "@/lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats().then(setStats).catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="flex items-center gap-2 text-[var(--destructive)] p-4">
        <AlertCircle className="h-5 w-5" />
        Failed to load dashboard: {error}
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-[var(--radius)] bg-[var(--muted)]"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats cards — catalog-ui Card style */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          icon={<Database className="h-4 w-4" />}
          label="Collections"
          value={stats.total_collections}
          color="text-blue-500"
        />
        <StatCard
          icon={<FileText className="h-4 w-4" />}
          label="Documents"
          value={stats.total_documents.toLocaleString()}
          color="text-emerald-500"
        />
        <StatCard
          icon={<Layers className="h-4 w-4" />}
          label="Chunks"
          value={stats.total_chunks.toLocaleString()}
          color="text-violet-500"
        />
        <StatCard
          icon={<CheckCircle className="h-4 w-4" />}
          label="Embedded"
          value={stats.embedded_chunks.toLocaleString()}
          color="text-teal-500"
        />
        <StatCard
          icon={<Percent className="h-4 w-4" />}
          label="Coverage"
          value={`${stats.coverage_pct}%`}
          color="text-amber-500"
        />
      </div>

      {/* Embedding model info card */}
      <div
        className="rounded-[var(--radius)] border p-4"
        style={{ background: "var(--card)", color: "var(--card-foreground)" }}
      >
        <div className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
          Embedding Model
        </div>
        <div className="text-lg font-semibold">
          {stats.embedding_model || "Not configured"}
          <span className="text-sm font-normal text-[var(--muted-foreground)] ml-2">
            ({stats.embedding_provider || "none"})
          </span>
        </div>
      </div>

      {/* Recent jobs */}
      <div
        className="rounded-[var(--radius)] border"
        style={{ background: "var(--card)" }}
      >
        <div className="px-4 py-3 border-b">
          <h2 className="text-sm font-semibold">Recent Jobs</h2>
        </div>
        <div className="p-4">
          {stats.recent_jobs.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">No recent jobs</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[var(--muted-foreground)] text-xs uppercase tracking-wider">
                  <th className="text-left py-2 font-medium">ID</th>
                  <th className="text-left py-2 font-medium">Type</th>
                  <th className="text-left py-2 font-medium">Status</th>
                  <th className="text-right py-2 font-medium">Items</th>
                  <th className="text-right py-2 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_jobs.map((job) => (
                  <tr key={job.id} className="border-t border-[var(--border)]">
                    <td className="py-2.5">{job.id}</td>
                    <td className="py-2.5">{job.job_type}</td>
                    <td className="py-2.5">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="py-2.5 text-right">
                      {job.processed_items}/{job.total_items}
                    </td>
                    <td className="py-2.5 text-right text-[var(--muted-foreground)] text-xs">
                      {new Date(job.started_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div
      className="rounded-[var(--radius)] border p-4"
      style={{ background: "var(--card)" }}
    >
      <div className="flex items-center gap-1.5 mb-2">
        <span className={color}>{icon}</span>
        <span className="text-xs font-medium text-[var(--muted-foreground)]">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
    failed: "bg-red-50 text-red-700 border-red-200",
    running: "bg-amber-50 text-amber-700 border-amber-200",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[status] || "bg-gray-50 text-gray-700 border-gray-200"}`}
    >
      {status}
    </span>
  );
}
