"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { CommandSettings } from "@/features/settings/components/command-settings"
import { FileBrowserSettings } from "@/features/settings/components/file-browser-settings"
import { InfraSettings } from "@/features/settings/components/infra-settings"
import { LdapSettings } from "@/features/settings/components/ldap-settings"
import { SecuritySettings } from "@/features/settings/components/security-settings"

export default function SettingsPage() {
  return (
    <>
      <DashboardHeader title="Settings" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Tabs defaultValue="infra">
          <TabsList variant="line">
            <TabsTrigger value="infra">Infra</TabsTrigger>
            <TabsTrigger value="ldap">LDAP</TabsTrigger>
            <TabsTrigger value="command">Command</TabsTrigger>
            <TabsTrigger value="file-browser">File Browser</TabsTrigger>
            <TabsTrigger value="security">Security</TabsTrigger>
          </TabsList>
          <TabsContent value="infra" className="mt-4">
            <InfraSettings />
          </TabsContent>
          <TabsContent value="ldap" className="mt-4">
            <LdapSettings />
          </TabsContent>
          <TabsContent value="command" className="mt-4">
            <CommandSettings />
          </TabsContent>
          <TabsContent value="file-browser" className="mt-4">
            <FileBrowserSettings />
          </TabsContent>
          <TabsContent value="security" className="mt-4">
            <SecuritySettings />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
