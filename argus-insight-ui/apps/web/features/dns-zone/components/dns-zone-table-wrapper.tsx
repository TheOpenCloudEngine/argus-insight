/**
 * DNS Zone Table Wrapper component.
 *
 * Handles health status states before showing the records grid:
 * - checking:       loading spinner
 * - not_configured: red error + "Go to PowerDNS Settings" button
 * - unreachable:    red error + "Go to PowerDNS Settings" button
 * - zone_missing:   zone not found message + "Create Zone" button
 * - ready:          records grid (or record-level error with Retry)
 */

"use client"

import { useRouter } from "next/navigation"
import { Loader2, Plus, Settings } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { DnsZoneTable } from "./dns-zone-table"
import { useDnsZone } from "./dns-zone-provider"

export function DnsZoneTableWrapper() {
  const {
    records, isLoading, error,
    healthStatus, healthError, zone,
    refreshRecords, handleCreateZone, creatingZone,
  } = useDnsZone()
  const router = useRouter()

  // 1) Initial health check in progress
  if (healthStatus === "checking") {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          Checking PowerDNS connection...
        </span>
      </div>
    )
  }

  // 2) PowerDNS not configured or unreachable → go to settings
  if (healthStatus === "not_configured" || healthStatus === "unreachable") {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <p className="text-sm text-destructive">
          {healthStatus === "not_configured"
            ? "PowerDNS must be configured in Settings > Domain > PowerDNS before using this feature."
            : healthError ?? "Cannot connect to PowerDNS server."}
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push("/dashboard/settings?tab=domain")}
        >
          <Settings className="h-4 w-4 mr-1.5" />
          Go to PowerDNS Settings
        </Button>
      </div>
    )
  }

  // 3) PowerDNS reachable but zone doesn't exist → create zone
  if (healthStatus === "zone_missing") {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <p className="text-sm text-muted-foreground">
          Zone &apos;{zone}&apos; does not exist on the PowerDNS server.
        </p>
        {healthError && (
          <p className="text-sm text-destructive">{healthError}</p>
        )}
        <Button
          size="sm"
          onClick={handleCreateZone}
          disabled={creatingZone}
        >
          {creatingZone ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
          ) : (
            <Plus className="h-4 w-4 mr-1.5" />
          )}
          Create Zone
        </Button>
      </div>
    )
  }

  // 4) Ready but record-level error
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

  // 5) Ready — show records grid
  return <DnsZoneTable data={records} isLoading={isLoading} />
}
