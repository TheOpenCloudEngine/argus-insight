"use client"

import { useCallback, useEffect, useState } from "react"
import {
  BookOpen,
  Database,
  Server,
  Tags,
} from "lucide-react"
import Link from "next/link"

import { Badge } from "@workspace/ui/components/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { DashboardHeader } from "@/components/dashboard-header"

type CatalogStats = {
  total_datasets: number
  total_platforms: number
  total_tags: number
  total_glossary_terms: number
  datasets_by_platform: { platform: string; count: number }[]
  datasets_by_origin: { origin: string; count: number }[]
  recent_datasets: {
    id: number
    name: string
    platform_name: string
    platform_display_name: string
    description: string | null
    origin: string
    status: string
    updated_at: string
  }[]
}

export default function DashboardPage() {
  const [stats, setStats] = useState<CatalogStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/catalog/stats")
      if (res.ok) {
        setStats(await res.json())
      }
    } catch {
      // ignore
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  return (
    <>
      <DashboardHeader title="Data Catalog" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Stats cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Datasets</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {isLoading ? "-" : stats?.total_datasets ?? 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Total registered datasets
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Platforms</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {isLoading ? "-" : stats?.total_platforms ?? 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Data platforms configured
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Tags</CardTitle>
              <Tags className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {isLoading ? "-" : stats?.total_tags ?? 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Classification tags
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Glossary Terms</CardTitle>
              <BookOpen className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {isLoading ? "-" : stats?.total_glossary_terms ?? 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Business glossary terms
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Datasets by platform and recent datasets */}
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Datasets by Platform</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <p className="text-sm text-muted-foreground">Loading...</p>
              ) : stats?.datasets_by_platform.length ? (
                <div className="space-y-3">
                  {stats.datasets_by_platform.map((item) => (
                    <div key={item.platform} className="flex items-center justify-between">
                      <span className="text-sm font-medium">{item.platform}</span>
                      <Badge variant="secondary">{item.count}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No datasets yet</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Datasets</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <p className="text-sm text-muted-foreground">Loading...</p>
              ) : stats?.recent_datasets.length ? (
                <div className="space-y-3">
                  {stats.recent_datasets.map((ds) => (
                    <Link
                      key={ds.id}
                      href={`/dashboard/datasets/${ds.id}`}
                      className="flex items-center justify-between rounded-md p-2 hover:bg-muted transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{ds.name}</p>
                        <p className="text-xs text-muted-foreground truncate">
                          {ds.platform_display_name}
                        </p>
                      </div>
                      <Badge variant="outline" className="ml-2 shrink-0">
                        {ds.origin}
                      </Badge>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No datasets yet</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Datasets by origin */}
        {stats?.datasets_by_origin.length ? (
          <Card>
            <CardHeader>
              <CardTitle>Datasets by Environment</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4">
                {stats.datasets_by_origin.map((item) => (
                  <div key={item.origin} className="flex items-center gap-2">
                    <Badge variant="outline">{item.origin}</Badge>
                    <span className="text-sm font-medium">{item.count} datasets</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </>
  )
}
