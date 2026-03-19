/**
 * DNS Zone Table Wrapper component.
 *
 * Connects the DnsZoneTable to the DnsZoneProvider context.
 * Displays error state when DNS records cannot be loaded.
 */

"use client"

import { Button } from "@workspace/ui/components/button"
import { DnsZoneTable } from "./dns-zone-table"
import { useDnsZone } from "./dns-zone-provider"

export function DnsZoneTableWrapper() {
  const { records, isLoading, error, refreshRecords } = useDnsZone()

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" onClick={refreshRecords}>
          Retry
        </Button>
      </div>
    )
  }

  return <DnsZoneTable data={records} isLoading={isLoading} />
}
