"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { OciModelRegistrySettings } from "@/features/settings/oci-model-registry-settings"

export default function SettingsPage() {
  return (
    <>
      <DashboardHeader title="Settings" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Tabs defaultValue="oci-model-registry">
          <TabsList>
            <TabsTrigger value="oci-model-registry">OCI Model Registry</TabsTrigger>
          </TabsList>
          <TabsContent value="oci-model-registry" className="mt-4">
            <OciModelRegistrySettings />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
