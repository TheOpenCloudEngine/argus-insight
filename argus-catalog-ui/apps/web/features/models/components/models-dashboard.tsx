"use client"

import { useCallback, useEffect, useState } from "react"
import { Box, GitBranch, CheckCircle2, AlertTriangle, Activity } from "lucide-react"
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { fetchModelStats, type ModelStats } from "../api"

/** Format bytes to human-readable string. */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** Shorten model name for chart labels. */
function shortName(name: string): string {
  const parts = name.split(".")
  return parts[parts.length - 1]
}

/** Format date label for line chart. */
function shortDate(dateStr: string): string {
  const parts = dateStr.split("-")
  return `${parts[1]}/${parts[2]}`
}

const STATUS_COLORS: Record<string, string> = {
  READY: "#3b82f6",
  PENDING: "#a1a1aa",
  FAILED: "#ef4444",
}

export function ModelsDashboard() {
  const [stats, setStats] = useState<ModelStats | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setStats(await fetchModelStats())
    } catch (err) {
      console.error("Failed to fetch model stats:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading || !stats) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[...Array(5)].map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-6">
              <div className="h-16 animate-pulse bg-muted rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const sizeData = stats.model_sizes.map((m) => ({
    name: shortName(m.model_name),
    fullName: m.model_name,
    size: m.model_size_bytes,
    sizeLabel: formatSize(m.model_size_bytes),
  }))

  const versionData = stats.versions_per_model.map((m) => ({
    name: shortName(m.model_name),
    fullName: m.model_name,
    versions: m.version_count,
  }))

  const pieData = stats.status_distribution.filter((s) => s.count > 0)

  const daily1dData = stats.daily_access_1d.map((d) => ({
    date: d.date,
    fullDate: d.date,
    count: d.count,
  }))

  const daily7dData = stats.daily_access_7d.map((d) => ({
    date: shortDate(d.date),
    fullDate: d.date,
    count: d.count,
  }))

  const daily30dData = stats.daily_access_30d.map((d) => ({
    date: shortDate(d.date),
    fullDate: d.date,
    count: d.count,
  }))

  const pub1dData = stats.daily_publish_1d.map((d) => ({
    date: d.date,
    fullDate: d.date,
    count: d.count,
  }))

  const pub7dData = stats.daily_publish_7d.map((d) => ({
    date: shortDate(d.date),
    fullDate: d.date,
    count: d.count,
  }))

  const pub30dData = stats.daily_publish_30d.map((d) => ({
    date: shortDate(d.date),
    fullDate: d.date,
    count: d.count,
  }))

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Models</CardTitle>
            <Box className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_models}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Versions</CardTitle>
            <GitBranch className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_versions}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Ready</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-500">{stats.ready_models}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {stats.ready_versions} version{stats.ready_versions !== 1 ? "s" : ""}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pending / Failed</CardTitle>
            <AlertTriangle className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              <span className="text-zinc-400">{stats.pending_count}</span>
              <span className="text-muted-foreground mx-1">/</span>
              <span className="text-red-500">{stats.failed_count}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Access</CardTitle>
            <Activity className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-500">{stats.total_access}</div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Pie: Version Status */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Version Status</CardTitle>
          </CardHeader>
          <CardContent>
            {pieData.length > 0 ? (
              <div className="flex items-center gap-4">
                <ResponsiveContainer width={140} height={140}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="count"
                      nameKey="status"
                      cx="50%"
                      cy="50%"
                      innerRadius={35}
                      outerRadius={60}
                      paddingAngle={2}
                    >
                      {pieData.map((entry) => (
                        <Cell
                          key={entry.status}
                          fill={STATUS_COLORS[entry.status] || "#a1a1aa"}
                        />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2">
                  {stats.status_distribution.map((s) => (
                    <div key={s.status} className="flex items-center gap-2 text-sm">
                      <span
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: STATUS_COLORS[s.status] || "#a1a1aa" }}
                      />
                      <span className="text-muted-foreground">{s.status}</span>
                      <span className="font-medium ml-auto">{s.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No data</p>
            )}
          </CardContent>
        </Card>

        {/* Bar: Model Size */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Model Size</CardTitle>
          </CardHeader>
          <CardContent>
            {sizeData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={sizeData}
                  layout="vertical"
                  margin={{ left: 0, right: 10, top: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis
                    type="number"
                    tickFormatter={(v) => formatSize(v)}
                    fontSize={11}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={90}
                    fontSize={11}
                  />
                  <Tooltip
                    formatter={(value: number) => formatSize(value)}
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.fullName || ""
                    }
                  />
                  <Bar dataKey="size" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No data</p>
            )}
          </CardContent>
        </Card>

        {/* Bar: Versions per Model */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Versions per Model</CardTitle>
          </CardHeader>
          <CardContent>
            {versionData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={versionData}
                  layout="vertical"
                  margin={{ left: 0, right: 10, top: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} fontSize={11} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={90}
                    fontSize={11}
                  />
                  <Tooltip
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.fullName || ""
                    }
                  />
                  <Bar dataKey="versions" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No data</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2: Access Trends */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Hourly Access (1 day) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Hourly Access (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            {daily1dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={daily1dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No access data yet</p>
            )}
          </CardContent>
        </Card>

        {/* Daily Access (7 days) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Daily Access (7 days)</CardTitle>
          </CardHeader>
          <CardContent>
            {daily7dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={daily7dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.fullDate || ""
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No access data yet</p>
            )}
          </CardContent>
        </Card>

        {/* Daily Access (30 days) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Daily Access (30 days)</CardTitle>
          </CardHeader>
          <CardContent>
            {daily30dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={daily30dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.fullDate || ""
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No access data yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 3: Publish Trends */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Hourly Publish (1 day) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Hourly Publish (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            {pub1dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={pub1dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#a855f7" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No publish data yet</p>
            )}
          </CardContent>
        </Card>

        {/* Daily Publish (7 days) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Daily Publish (7 days)</CardTitle>
          </CardHeader>
          <CardContent>
            {pub7dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={pub7dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.fullDate || ""
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#d946ef"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No publish data yet</p>
            )}
          </CardContent>
        </Card>

        {/* Daily Publish (30 days) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Daily Publish (30 days)</CardTitle>
          </CardHeader>
          <CardContent>
            {pub30dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={pub30dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.fullDate || ""
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No publish data yet</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
