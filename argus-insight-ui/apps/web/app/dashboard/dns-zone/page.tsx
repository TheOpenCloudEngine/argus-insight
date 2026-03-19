"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { DnsZoneDialogs } from "@/features/dns-zone/components/dns-zone-dialogs"
import { DnsZoneProvider } from "@/features/dns-zone/components/dns-zone-provider"
import { DnsZoneTableWrapper } from "@/features/dns-zone/components/dns-zone-table-wrapper"

export default function DnsZonePage() {
  return (
    <DnsZoneProvider>
      <DashboardHeader title="Domain Zone" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <DnsZoneTableWrapper />
      </div>

      <DnsZoneDialogs />
    </DnsZoneProvider>
  )
}
