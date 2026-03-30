"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { DashboardHeader } from "@/components/dashboard-header"

import type { PluginResponse } from "@/features/software-deployment/types"
import { fetchPlugins } from "@/features/software-deployment/api"
import { PipelineTab } from "@/features/software-deployment/components/pipeline-tab"
import { CatalogTab } from "@/features/software-deployment/components/catalog-tab"
import { CatalogCardTab } from "@/features/software-deployment/components/catalog-card-tab"

export default function SoftwareDeploymentPage() {
  const [plugins, setPlugins] = useState<PluginResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const loadPlugins = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true)
      setError(null)
      const data = await fetchPlugins()
      setPlugins(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load plugins")
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPlugins()
  }, [loadPlugins])

  if (loading) {
    return (
      <>
        <DashboardHeader title="Software Deployment" />
        <div className="flex flex-1 items-center justify-center p-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </>
    )
  }

  if (error) {
    return (
      <>
        <DashboardHeader title="Software Deployment" />
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={loadPlugins}>
            Retry
          </Button>
        </div>
      </>
    )
  }

  return (
    <>
      <DashboardHeader title="Software Deployment" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Tabs defaultValue="pipeline">
          <TabsList variant="line">
            <TabsTrigger value="pipeline" className="text-base">
              Pipeline
            </TabsTrigger>
            <TabsTrigger value="catalog" className="text-base">
              Plugin Catalog
            </TabsTrigger>
            <TabsTrigger value="catalog-card" className="text-base">
              Plugin Catalog (Card)
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pipeline" className="mt-4">
            <PipelineTab plugins={plugins} onRefresh={() => loadPlugins(false)} />
          </TabsContent>

          <TabsContent value="catalog" className="mt-4">
            <CatalogTab plugins={plugins} onPluginsChanged={() => loadPlugins(false)} />
          </TabsContent>

          <TabsContent value="catalog-card" className="mt-4">
            <CatalogCardTab plugins={plugins} onPluginsChanged={() => loadPlugins(false)} />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
