"use client"

import { useCallback, useEffect, useState } from "react"
import {
  BookOpen, Database, Server, Tags, Users, RefreshCw,
} from "lucide-react"
import Link from "next/link"
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from "recharts"

import { Badge } from "@workspace/ui/components/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { DashboardHeader } from "@/components/dashboard-header"

type CatalogStats = {
  total_datasets: number
  total_platforms: number
  total_tags: number
  total_glossary_terms: number
  total_owners: number
  synced_datasets: number
  datasets_by_platform: { platform: string; count: number }[]
  datasets_by_origin: { origin: string; count: number }[]
  datasets_by_platform_type: { type: string; count: number }[]
  schema_fields_by_platform: { platform: string; count: number }[]
  top_tagged_datasets: { name: string; count: number }[]
  daily_datasets_1d: { date: string; count: number }[]
  daily_datasets_7d: { date: string; count: number }[]
  daily_datasets_30d: { date: string; count: number }[]
  recent_datasets: {
    id: number
    name: string
    platform_name: string
    platform_type: string
    description: string | null
    origin: string
    status: string
    tag_count: number
    owner_count: number
    schema_field_count: number
    updated_at: string
  }[]
}

function shortName(name: string): string {
  return name.length > 18 ? name.slice(0, 16) + "..." : name
}

function shortDate(dateStr: string): string {
  const parts = dateStr.split("-")
  return `${parts[1]}/${parts[2]}`
}

const PLATFORM_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#6366f1",
]

const ORIGIN_COLORS: Record<string, string> = {
  PROD: "#3b82f6",
  DEV: "#f59e0b",
  STAGING: "#10b981",
}

export default function DashboardPage() {
  const [stats, setStats] = useState<CatalogStats | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true)
      const res = await fetch("/api/v1/catalog/stats")
      if (res.ok) setStats(await res.json())
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])

  if (loading || !stats) {
    return (
      <>
        <DashboardHeader title="Data Catalog" />
        <div className="flex flex-1 flex-col gap-4 p-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
            {[...Array(6)].map((_, i) => (
              <Card key={i}><CardContent className="pt-6"><div className="h-16 animate-pulse bg-muted rounded" /></CardContent></Card>
            ))}
          </div>
        </div>
      </>
    )
  }

  const platformBarData = stats.datasets_by_platform.slice(0, 10).map((d) => ({
    name: shortName(d.platform), fullName: d.platform, count: d.count,
  }))

  // Show top 5 platform types, group the rest as "Others"
  const platformTypeRaw = stats.datasets_by_platform_type.filter((d) => d.count > 0)
  const platformTypeData = platformTypeRaw.length <= 6
    ? platformTypeRaw
    : [
        ...platformTypeRaw.slice(0, 5),
        { type: "Others", count: platformTypeRaw.slice(5).reduce((s, d) => s + d.count, 0) },
      ]
  const originData = stats.datasets_by_origin.filter((d) => d.count > 0)

  const schemaData = stats.schema_fields_by_platform.map((d) => ({
    name: shortName(d.platform), fullName: d.platform, count: d.count,
  }))

  const tagData = stats.top_tagged_datasets.map((d) => ({
    name: shortName(d.name), fullName: d.name, count: d.count,
  }))

  const ds1dData = stats.daily_datasets_1d.map((d) => ({ date: d.date, fullDate: d.date, count: d.count }))
  const ds7dData = stats.daily_datasets_7d.map((d) => ({ date: shortDate(d.date), fullDate: d.date, count: d.count }))
  const ds30dData = stats.daily_datasets_30d.map((d) => ({ date: shortDate(d.date), fullDate: d.date, count: d.count }))

  return (
    <>
      <DashboardHeader title="Data Catalog" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Summary Cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Datasets</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_datasets}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Platforms</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_platforms}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Tags</CardTitle>
              <Tags className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-500">{stats.total_tags}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Glossary</CardTitle>
              <BookOpen className="h-4 w-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-purple-500">{stats.total_glossary_terms}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Owners</CardTitle>
              <Users className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-500">{stats.total_owners}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Synced</CardTitle>
              <RefreshCw className="h-4 w-4 text-emerald-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-emerald-500">{stats.synced_datasets}</div>
              <p className="text-xs text-muted-foreground">
                / {stats.total_datasets} datasets
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Charts Row 1: Distribution */}
        <div className="grid gap-4 lg:grid-cols-3">
          {/* Donut: Platform Type */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Platform Type Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              {platformTypeData.length > 0 ? (
                <div className="flex items-center gap-4">
                  <ResponsiveContainer width={140} height={140}>
                    <PieChart>
                      <Pie
                        data={platformTypeData}
                        dataKey="count"
                        nameKey="type"
                        cx="50%"
                        cy="50%"
                        innerRadius={35}
                        outerRadius={60}
                        paddingAngle={2}
                      >
                        {platformTypeData.map((_, i) => (
                          <Cell key={i} fill={PLATFORM_COLORS[i % PLATFORM_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-1.5">
                    {platformTypeData.map((s, i) => (
                      <div key={s.type} className="flex items-center gap-2 text-sm">
                        <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: PLATFORM_COLORS[i % PLATFORM_COLORS.length] }} />
                        <span className="text-muted-foreground truncate">{s.type}</span>
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

          {/* Donut: Origin */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Origin Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              {originData.length > 0 ? (
                <div className="flex items-center gap-4">
                  <ResponsiveContainer width={140} height={140}>
                    <PieChart>
                      <Pie
                        data={originData}
                        dataKey="count"
                        nameKey="origin"
                        cx="50%"
                        cy="50%"
                        innerRadius={35}
                        outerRadius={60}
                        paddingAngle={2}
                      >
                        {originData.map((entry) => (
                          <Cell key={entry.origin} fill={ORIGIN_COLORS[entry.origin] || "#a1a1aa"} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-2">
                    {originData.map((s) => (
                      <div key={s.origin} className="flex items-center gap-2 text-sm">
                        <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: ORIGIN_COLORS[s.origin] || "#a1a1aa" }} />
                        <span className="text-muted-foreground">{s.origin}</span>
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

          {/* Bar: Top Platforms */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Top Platforms by Dataset</CardTitle>
            </CardHeader>
            <CardContent>
              {platformBarData.length > 0 ? (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={platformBarData} layout="vertical" margin={{ left: 0, right: 10, top: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} fontSize={11} />
                    <YAxis type="category" dataKey="name" width={90} fontSize={11} />
                    <Tooltip labelFormatter={(_, p) => p?.[0]?.payload?.fullName || ""} />
                    <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">No data</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Charts Row 2: Dataset Growth Trends */}
        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Hourly New Datasets (24h)</CardTitle>
            </CardHeader>
            <CardContent>
              {ds1dData.length > 0 ? (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={ds1dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" fontSize={10} />
                    <YAxis allowDecimals={false} fontSize={11} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">No data yet</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Daily New Datasets (7 days)</CardTitle>
            </CardHeader>
            <CardContent>
              {ds7dData.length > 0 ? (
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart data={ds7dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" fontSize={10} />
                    <YAxis allowDecimals={false} fontSize={11} />
                    <Tooltip labelFormatter={(_, p) => p?.[0]?.payload?.fullDate || ""} />
                    <Line type="monotone" dataKey="count" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">No data yet</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Daily New Datasets (30 days)</CardTitle>
            </CardHeader>
            <CardContent>
              {ds30dData.length > 0 ? (
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart data={ds30dData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" fontSize={10} />
                    <YAxis allowDecimals={false} fontSize={11} />
                    <Tooltip labelFormatter={(_, p) => p?.[0]?.payload?.fullDate || ""} />
                    <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">No data yet</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Charts Row 3: Schema & Tags */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Bar: Schema Fields by Platform */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Schema Fields by Platform</CardTitle>
            </CardHeader>
            <CardContent>
              {schemaData.length > 0 ? (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={schemaData} layout="vertical" margin={{ left: 0, right: 10, top: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} fontSize={11} />
                    <YAxis type="category" dataKey="name" width={90} fontSize={11} />
                    <Tooltip labelFormatter={(_, p) => p?.[0]?.payload?.fullName || ""} />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">No schema data</p>
              )}
            </CardContent>
          </Card>

          {/* Bar: Top Tagged Datasets */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Top Tagged Datasets</CardTitle>
            </CardHeader>
            <CardContent>
              {tagData.length > 0 ? (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={tagData} layout="vertical" margin={{ left: 0, right: 10, top: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} fontSize={11} />
                    <YAxis type="category" dataKey="name" width={90} fontSize={11} />
                    <Tooltip labelFormatter={(_, p) => p?.[0]?.payload?.fullName || ""} />
                    <Bar dataKey="count" fill="#ec4899" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">No tagged datasets</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Recent Datasets Table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Recent Datasets</CardTitle>
          </CardHeader>
          <CardContent>
            {stats.recent_datasets.length > 0 ? (
              <div className="border rounded-md overflow-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/60">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Name</th>
                      <th className="px-3 py-2 text-left font-medium w-36">Platform</th>
                      <th className="px-3 py-2 text-center font-medium w-20">Origin</th>
                      <th className="px-3 py-2 text-center font-medium w-16">Tags</th>
                      <th className="px-3 py-2 text-center font-medium w-16">Owners</th>
                      <th className="px-3 py-2 text-center font-medium w-16">Fields</th>
                      <th className="px-3 py-2 text-left font-medium w-28">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {stats.recent_datasets.map((ds) => (
                      <tr key={ds.id} className="hover:bg-muted/30">
                        <td className="px-3 py-2">
                          <Link
                            href={`/dashboard/datasets/${ds.id}`}
                            className="font-medium hover:underline"
                          >
                            {ds.name}
                          </Link>
                          {ds.description && (
                            <p className="text-xs text-muted-foreground truncate max-w-[400px]">{ds.description}</p>
                          )}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">{ds.platform_name}</td>
                        <td className="px-3 py-2 text-center">
                          <Badge variant="outline" className="text-xs">{ds.origin}</Badge>
                        </td>
                        <td className="px-3 py-2 text-center text-muted-foreground">{ds.tag_count}</td>
                        <td className="px-3 py-2 text-center text-muted-foreground">{ds.owner_count}</td>
                        <td className="px-3 py-2 text-center text-muted-foreground">{ds.schema_field_count}</td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {new Date(ds.updated_at).toLocaleDateString("en-US", {
                            month: "short", day: "numeric", year: "numeric",
                          })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No datasets yet</p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
