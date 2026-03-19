/**
 * DNS Zone Management page.
 *
 * This is the main page component for the DNS zone management feature,
 * accessible at /dashboard/dns-zone. It provides a complete interface
 * for viewing and managing DNS records in the configured PowerDNS zone.
 *
 * The page is structured with three layers:
 *
 * 1. **DnsZoneProvider** - Context provider that wraps all child components.
 *    Manages the PowerDNS health state machine, record data, dialog state,
 *    and row selection state. Runs a health check on mount.
 *
 * 2. **DnsZoneTableWrapper** - Conditional renderer that shows different
 *    views based on the health status (loading, error, zone creation, or
 *    the full records data table).
 *
 * 3. **DnsZoneDialogs** - Centralized dialog mount point for all modal
 *    dialogs (add, edit, delete, bulk delete, BIND config export).
 *
 * This is a client component ("use client") because it uses React context,
 * state, and effects for interactive DNS record management.
 */

"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { DnsZoneDialogs } from "@/features/dns-zone/components/dns-zone-dialogs"
import { DnsZoneProvider } from "@/features/dns-zone/components/dns-zone-provider"
import { DnsZoneTableWrapper } from "@/features/dns-zone/components/dns-zone-table-wrapper"

/** DNS Zone page component rendered at /dashboard/dns-zone. */
export default function DnsZonePage() {
  return (
    <DnsZoneProvider>
      {/* Page header with "Domain Zone" title */}
      <DashboardHeader title="Domain Zone" />

      {/* Main content area: health-status-driven table or status message */}
      <div className="flex flex-1 flex-col gap-4 p-4">
        <DnsZoneTableWrapper />
      </div>

      {/* All modal dialogs (add, edit, delete, bulk-delete, bind-conf) */}
      <DnsZoneDialogs />
    </DnsZoneProvider>
  )
}
