"use client"

import { useCallback, useEffect, useState } from "react"
import { Box, Download, GitBranch, Globe, Upload, Activity } from "lucide-react"
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { fetchOciHubStats, type OciHubStats } from "./api"

function formatSize(bytes: number): string {
  if (!bytes) return "-"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function shortName(name: string): string {
  return name.length > 20 ? name.slice(0, 18) + "..." : name
}

function shortDate(dateStr: string): string {
  const parts = dateStr.split("-")
  return `${parts[1]}/${parts[2]}`
}

const SOURCE_COLORS: Record<string, string> = {
  huggingface: "#3b82f6",
  my: "#f97316",
  file: "#10b981",
  local: "#10b981",
  unknown: "#a1a1aa",
}

export function OciHubDashboard() {
  const [stats, setStats] = useState<OciHubStats | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setStats(await fetchOciHubStats())
    } catch (err) {
      console.error("Failed to fetch OCI Hub stats:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading || !stats) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        {[...Array(6)].map((_, i) => (
          <Card key={i}><CardContent className="pt-6"><div className="h-16 animate-pulse bg-muted rounded" /></CardContent></Card>
        ))}
      </div>
    )
  }

  const pieData = stats.source_distribution.filter((s) => s.count > 0)
  const sizeData = stats.model_sizes.map((m) => ({ name: shortName(m.model_name), fullName: m.model_name, size: m.total_size }))
  const dlData = stats.top_downloads.map((m) => ({ name: shortName(m.model_name), fullName: m.model_name, downloads: m.download_count }))

  const dl1dData = stats.download_1d.map((d) => ({ date: d.date, fullDate: d.date, count: d.count }))
  const dl7dData = stats.download_7d.map((d) => ({ date: shortDate(d.date), fullDate: d.date, count: d.count }))
  const dl30dData = stats.download_30d.map((d) => ({ date: shortDate(d.date), fullDate: d.date, count: d.count }))

  const pub1dData = stats.publish_1d.map((d) => ({ date: d.date, fullDate: d.date, count: d.count }))
  const pub7dData = stats.publish_7d.map((d) => ({ date: shortDate(d.date), fullDate: d.date, count: d.count }))
  const pub30dData = stats.publish_30d.map((d) => ({ date: shortDate(d.date), fullDate: d.date, count: d.count }))

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
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
            <CardTitle className="text-sm font-medium">HuggingFace</CardTitle>
            <Globe className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-500">{stats.hf_count}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">My Models</CardTitle>
            <Upload className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-500">{stats.my_count}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Download</CardTitle>
            <Download className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-500">{stats.total_download}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Publish</CardTitle>
            <Activity className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-500">{stats.total_publish}</div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1: Source / Size / Downloads */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Donut: Source Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Source Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {pieData.length > 0 ? (
              <div className="flex items-center gap-4">
                <ResponsiveContainer width={140} height={140}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="count"
                      nameKey="source"
                      cx="50%"
                      cy="50%"
                      innerRadius={35}
                      outerRadius={60}
                      paddingAngle={2}
                    >
                      {pieData.map((entry) => (
                        <Cell key={entry.source} fill={SOURCE_COLORS[entry.source] || "#a1a1aa"} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2">
                  {pieData.map((s) => (
                    <div key={s.source} className="flex items-center gap-2 text-sm">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: SOURCE_COLORS[s.source] || "#a1a1aa" }} />
                      <span className="text-muted-foreground">{s.source}</span>
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

        {/* Bar: Model Size Top 10 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Model Size (Top 10)</CardTitle>
          </CardHeader>
          <CardContent>
            {sizeData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={sizeData} layout="vertical" margin={{ left: 0, right: 10, top: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => formatSize(v)} fontSize={11} />
                  <YAxis type="category" dataKey="name" width={90} fontSize={11} />
                  <Tooltip formatter={(value: number) => formatSize(value)} labelFormatter={(_, p) => p?.[0]?.payload?.fullName || ""} />
                  <Bar dataKey="size" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No data</p>
            )}
          </CardContent>
        </Card>

        {/* Bar: Downloads Top 10 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Downloads (Top 10)</CardTitle>
          </CardHeader>
          <CardContent>
            {dlData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={dlData} layout="vertical" margin={{ left: 0, right: 10, top: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} fontSize={11} />
                  <YAxis type="category" dataKey="name" width={90} fontSize={11} />
                  <Tooltip labelFormatter={(_, p) => p?.[0]?.payload?.fullName || ""} />
                  <Bar dataKey="downloads" fill="#10b981" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No downloads yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2: Download Trends */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Hourly Download (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            {dl1dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={dl1dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No download data yet</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Daily Download (7 days)</CardTitle>
          </CardHeader>
          <CardContent>
            {dl7dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={dl7dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ""} />
                  <Line type="monotone" dataKey="count" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No download data yet</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Daily Download (30 days)</CardTitle>
          </CardHeader>
          <CardContent>
            {dl30dData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={dl30dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ""} />
                  <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No download data yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 3: Publish Trends */}
      <div className="grid gap-4 lg:grid-cols-3">
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
                  <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ""} />
                  <Line type="monotone" dataKey="count" stroke="#d946ef" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No publish data yet</p>
            )}
          </CardContent>
        </Card>

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
                  <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ""} />
                  <Line type="monotone" dataKey="count" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
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
