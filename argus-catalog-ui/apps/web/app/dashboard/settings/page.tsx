"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { OciModelRegistrySettings } from "@/features/settings/oci-model-registry-settings"
import { EmbeddingSettings } from "@/features/settings/embedding-settings"
import { LLMSettings } from "@/features/settings/llm-settings"
import { AuthSettings } from "@/features/settings/auth-settings"
import { CorsSettings } from "@/features/settings/cors-settings"
import { CacheSettings } from "@/features/settings/cache-settings"

export default function SettingsPage() {
  return (
    <>
      <DashboardHeader title="Settings" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Tabs defaultValue="auth">
          <TabsList>
            <TabsTrigger value="auth">Authentication</TabsTrigger>
            <TabsTrigger value="cors">CORS</TabsTrigger>
            <TabsTrigger value="oci-model-registry">OCI Model Registry</TabsTrigger>
            <TabsTrigger value="embedding">Embedding</TabsTrigger>
            <TabsTrigger value="llm">LLM / AI</TabsTrigger>
            <TabsTrigger value="cache">Cache</TabsTrigger>
          </TabsList>
          <TabsContent value="auth" className="mt-4">
            <AuthSettings />
          </TabsContent>
          <TabsContent value="cors" className="mt-4">
            <CorsSettings />
          </TabsContent>
          <TabsContent value="oci-model-registry" className="mt-4">
            <OciModelRegistrySettings />
          </TabsContent>
          <TabsContent value="embedding" className="mt-4">
            <EmbeddingSettings />
          </TabsContent>
          <TabsContent value="llm" className="mt-4">
            <LLMSettings />
          </TabsContent>
          <TabsContent value="cache" className="mt-4">
            <CacheSettings />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
