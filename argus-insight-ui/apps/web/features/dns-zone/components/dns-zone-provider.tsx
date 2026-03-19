/**
 * DNS Zone Context Provider.
 *
 * Manages all shared state for the DNS zone management page, including:
 * - PowerDNS health status (connection state machine)
 * - DNS records data fetched from the backend
 * - Dialog open/close state for add, edit, delete, and BIND export dialogs
 * - Row selection state for bulk operations
 *
 * On mount, the provider runs a health check against the PowerDNS server
 * via the backend API. Based on the result, it transitions through a
 * state machine that determines which UI to render:
 *
 * Health states (HealthStatus):
 * - "checking":       Initial health check in progress (shows spinner)
 * - "not_configured": PowerDNS settings are missing in the database
 *                     (shows "Go to PowerDNS Settings" button)
 * - "unreachable":    PowerDNS server cannot be reached or API key is invalid
 *                     (shows "Go to PowerDNS Settings" button with error)
 * - "zone_missing":   PowerDNS is reachable but the configured zone does not exist
 *                     (shows "Create Zone" button)
 * - "ready":          Everything is OK, records have been loaded
 *                     (shows the DNS records data table)
 */

"use client"

import React, { useCallback, useEffect, useState } from "react"

import useDialogState from "@/hooks/use-dialog-state"
import { checkDnsHealth, createZone, fetchZoneRecords } from "../api"
import { type DnsRecord } from "../data/schema"

/** Union type of all dialog identifiers managed by this provider. */
type DnsZoneDialogType = "add" | "edit" | "delete" | "bulk-delete" | "bind-conf"

/** Possible health states for the PowerDNS connection state machine. */
export type HealthStatus =
  | "checking"
  | "not_configured"
  | "unreachable"
  | "zone_missing"
  | "ready"

/**
 * Shape of the DNS zone context value.
 * All child components access this via the useDnsZone() hook.
 */
type DnsZoneContextType = {
  /** Currently open dialog type, or null if no dialog is open */
  open: DnsZoneDialogType | null
  /** Open or close a dialog by type (null to close) */
  setOpen: (type: DnsZoneDialogType | null) => void
  /** The record currently being edited or deleted (single-row action) */
  currentRow: DnsRecord | null
  /** Set the current row for edit/delete actions */
  setCurrentRow: React.Dispatch<React.SetStateAction<DnsRecord | null>>
  /** The record type selected in the "Add Record" dropdown (e.g. "A", "CNAME") */
  selectedRecordType: string
  /** Set the record type for the add dialog */
  setSelectedRecordType: (type: string) => void
  /** Records selected via checkboxes for bulk operations */
  selectedRecords: DnsRecord[]
  /** Update the set of selected records (synced from table row selection) */
  setSelectedRecords: React.Dispatch<React.SetStateAction<DnsRecord[]>>
  /** All DNS records currently loaded from the backend */
  records: DnsRecord[]
  /** The configured domain zone name (e.g. "example.com") */
  zone: string
  /** Whether records are currently being fetched */
  isLoading: boolean
  /** Error message from the last record fetch, or null */
  error: string | null
  /** Current state in the PowerDNS health state machine */
  healthStatus: HealthStatus
  /** Human-readable error from the health check, or null */
  healthError: string | null
  /** Re-run the full health check and reload records if healthy */
  refreshRecords: () => Promise<void>
  /** Create the zone on PowerDNS and re-run health check */
  handleCreateZone: () => Promise<void>
  /** Whether zone creation is currently in progress */
  creatingZone: boolean
}

const DnsZoneContext = React.createContext<DnsZoneContextType | null>(null)

/**
 * Provider component that wraps the DNS zone page.
 *
 * Initializes the health check on mount and provides all shared state
 * to child components via React context. All DNS zone components
 * (table, dialogs, buttons) consume this context through useDnsZone().
 */
export function DnsZoneProvider({ children }: { children: React.ReactNode }) {
  // Dialog state management (which dialog is currently open)
  const [open, setOpen] = useDialogState<DnsZoneDialogType>(null)

  // Single-row action state: the record being edited or deleted
  const [currentRow, setCurrentRow] = useState<DnsRecord | null>(null)

  // Record type selected from the "Add Record" dropdown menu
  const [selectedRecordType, setSelectedRecordType] = useState("")

  // Checkbox-selected records for bulk delete operations
  const [selectedRecords, setSelectedRecords] = useState<DnsRecord[]>([])

  // DNS records data loaded from the backend API
  const [records, setRecords] = useState<DnsRecord[]>([])
  const [zone, setZone] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // PowerDNS health state machine
  const [healthStatus, setHealthStatus] = useState<HealthStatus>("checking")
  const [healthError, setHealthError] = useState<string | null>(null)
  const [creatingZone, setCreatingZone] = useState(false)

  /**
   * Fetch DNS records from the backend API.
   * Only called when the health check confirms the zone exists and is ready.
   */
  const loadRecords = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const data = await fetchZoneRecords()
      setRecords(data.records)
      setZone(data.zone)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load DNS records")
      setRecords([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  /**
   * Run the full PowerDNS health check and transition the state machine.
   *
   * Checks connectivity, authentication, and zone existence in a single API call.
   * If the server is healthy and the zone exists, automatically loads records.
   * The health status drives which UI the DnsZoneTableWrapper renders.
   */
  const runHealthCheck = useCallback(async () => {
    try {
      setHealthStatus("checking")
      setHealthError(null)
      const health = await checkDnsHealth()

      setZone(health.zone)

      // Not reachable: distinguish between "not configured" and "unreachable"
      if (!health.reachable) {
        if (health.error?.includes("not configured")) {
          setHealthStatus("not_configured")
        } else {
          setHealthStatus("unreachable")
        }
        setHealthError(health.error ?? "Cannot connect to PowerDNS")
        return
      }

      // Reachable but has an error (e.g. invalid server_id) -> show settings
      if (health.error) {
        setHealthStatus("unreachable")
        setHealthError(health.error)
        return
      }

      // Reachable but the zone has not been created yet
      if (!health.zone_exists) {
        setHealthStatus("zone_missing")
        return
      }

      // Everything is OK -- load the records
      setHealthStatus("ready")
      await loadRecords()
    } catch (err) {
      setHealthStatus("unreachable")
      setHealthError(err instanceof Error ? err.message : "Health check failed")
    }
  }, [loadRecords])

  // Run health check on initial mount
  useEffect(() => {
    runHealthCheck()
  }, [runHealthCheck])

  /**
   * Refresh the DNS zone data by re-running the full health check.
   * Called after record mutations (add, edit, delete) to reload the table.
   */
  const refreshRecords = useCallback(async () => {
    await runHealthCheck()
  }, [runHealthCheck])

  /**
   * Create the configured zone on the PowerDNS server.
   * Called from the "Create Zone" button when healthStatus is "zone_missing".
   * After creation, re-runs the health check to transition to "ready" state.
   */
  const handleCreateZone = useCallback(async () => {
    try {
      setCreatingZone(true)
      setHealthError(null)
      await createZone()
      await runHealthCheck()
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : "Failed to create zone")
    } finally {
      setCreatingZone(false)
    }
  }, [runHealthCheck])

  return (
    <DnsZoneContext value={{
      open, setOpen,
      currentRow, setCurrentRow,
      selectedRecordType, setSelectedRecordType,
      selectedRecords, setSelectedRecords,
      records, zone, isLoading, error,
      healthStatus, healthError,
      refreshRecords,
      handleCreateZone, creatingZone,
    }}>
      {children}
    </DnsZoneContext>
  )
}

/**
 * Hook to access the DNS zone context.
 *
 * Must be called from a component that is a descendant of DnsZoneProvider.
 * Throws an error if used outside the provider to catch misuse early.
 *
 * @returns The DNS zone context value with all shared state and actions.
 */
export const useDnsZone = () => {
  const ctx = React.useContext(DnsZoneContext)
  if (!ctx) {
    throw new Error("useDnsZone must be used within <DnsZoneProvider>")
  }
  return ctx
}
