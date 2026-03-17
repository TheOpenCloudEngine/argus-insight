"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { CommandSettings } from "@/features/settings/components/command-settings"
import { FileBrowserSettings } from "@/features/settings/components/file-browser-settings"
import { DomainSettings } from "@/features/settings/components/domain-settings"
import { LdapSettings } from "@/features/settings/components/ldap-settings"
import { SecuritySettings } from "@/features/settings/components/security-settings"

export default function SettingsPage() {
  return (
    <>
      <DashboardHeader title="Settings" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Tabs defaultValue="domain">
          <TabsList variant="line">
            <TabsTrigger value="domain" className="text-base">Domain</TabsTrigger>
            <TabsTrigger value="ldap" className="text-base">LDAP</TabsTrigger>
            <TabsTrigger value="command" className="text-base">Command</TabsTrigger>
            <TabsTrigger value="file-browser" className="text-base">File Browser</TabsTrigger>
            <TabsTrigger value="security" className="text-base">Security</TabsTrigger>
          </TabsList>
          <TabsContent value="domain" className="mt-4">
            <DomainSettings />
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
