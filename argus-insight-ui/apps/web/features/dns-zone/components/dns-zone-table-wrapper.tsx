/**
 * DNS Zone Table Wrapper component.
 *
 * Acts as a state-driven UI router that renders different views based on
 * the current PowerDNS health status from the DnsZoneProvider context.
 * This component is the top-level content area of the DNS zone page.
 *
 * The rendering follows a priority-based decision tree:
 *
 * 1. **checking** (initial state):
 *    Shows a loading spinner while the health check API call is in progress.
 *
 * 2. **not_configured** / **unreachable**:
 *    Shows an error message and a "Go to PowerDNS Settings" button that
 *    navigates to the Settings page with the Domain tab pre-selected.
 *    "not_configured" means the database has no PowerDNS settings.
 *    "unreachable" means settings exist but the server cannot be contacted.
 *
 * 3. **zone_missing**:
 *    Shows a message that the zone does not exist and a "Create Zone" button.
 *    This happens when PowerDNS is reachable but the configured domain zone
 *    has not been created yet.
 *
 * 4. **ready** (with error):
 *    The health check passed but record fetching failed. Shows the error
 *    message with a "Retry" button.
 *
 * 5. **ready** (success):
 *    Everything is OK. Renders the DnsZoneTable with the loaded records.
 */

"use client"

import { useRouter } from "next/navigation"
import { Loader2, Plus, Settings } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { DnsZoneTable } from "./dns-zone-table"
import { useDnsZone } from "./dns-zone-provider"

/**
 * Wrapper component that conditionally renders the DNS zone table
 * or an appropriate status/error message based on the health check result.
 */
export function DnsZoneTableWrapper() {
  const {
    records, isLoading, error,
    healthStatus, healthError, zone,
    refreshRecords, handleCreateZone, creatingZone,
  } = useDnsZone()
  const router = useRouter()

  // 1) Initial health check in progress -- show spinner
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

  // 2) PowerDNS not configured or unreachable -- direct user to settings page
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

  // 3) PowerDNS reachable but zone doesn't exist -- offer zone creation
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

  // 4) Health check passed but record fetching failed -- show error with retry
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

  // 5) Everything is OK -- render the full records data table
  return <DnsZoneTable data={records} isLoading={isLoading} />
}
