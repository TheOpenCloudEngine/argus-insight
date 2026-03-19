/**
 * DNS Zone Context Provider.
 *
 * On mount, first checks PowerDNS health (connectivity + zone existence),
 * then fetches records only if everything is ready.
 *
 * Health states:
 * - checking:       initial health check in progress
 * - not_configured: PowerDNS settings missing → show "Go to PowerDNS Settings"
 * - unreachable:    PowerDNS server cannot be reached → show "Go to PowerDNS Settings"
 * - zone_missing:   PowerDNS reachable but zone doesn't exist → show "Create Zone"
 * - ready:          everything OK → show records grid
 */

"use client"

import React, { useCallback, useEffect, useState } from "react"

import useDialogState from "@/hooks/use-dialog-state"
import { checkDnsHealth, createZone, fetchZoneRecords } from "../api"
import { type DnsRecord } from "../data/schema"

type DnsZoneDialogType = "add" | "edit" | "delete"

export type HealthStatus =
  | "checking"
  | "not_configured"
  | "unreachable"
  | "zone_missing"
  | "ready"

type DnsZoneContextType = {
  open: DnsZoneDialogType | null
  setOpen: (type: DnsZoneDialogType | null) => void
  currentRow: DnsRecord | null
  setCurrentRow: React.Dispatch<React.SetStateAction<DnsRecord | null>>
  selectedRecordType: string
  setSelectedRecordType: (type: string) => void
  records: DnsRecord[]
  zone: string
  isLoading: boolean
  error: string | null
  healthStatus: HealthStatus
  healthError: string | null
  refreshRecords: () => Promise<void>
  handleCreateZone: () => Promise<void>
  creatingZone: boolean
}

const DnsZoneContext = React.createContext<DnsZoneContextType | null>(null)

export function DnsZoneProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useDialogState<DnsZoneDialogType>(null)
  const [currentRow, setCurrentRow] = useState<DnsRecord | null>(null)
  const [selectedRecordType, setSelectedRecordType] = useState("")
  const [records, setRecords] = useState<DnsRecord[]>([])
  const [zone, setZone] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [healthStatus, setHealthStatus] = useState<HealthStatus>("checking")
  const [healthError, setHealthError] = useState<string | null>(null)
  const [creatingZone, setCreatingZone] = useState(false)

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

  const runHealthCheck = useCallback(async () => {
    try {
      setHealthStatus("checking")
      setHealthError(null)
      const health = await checkDnsHealth()

      setZone(health.zone)

      if (!health.reachable) {
        if (health.error?.includes("not configured")) {
          setHealthStatus("not_configured")
        } else {
          setHealthStatus("unreachable")
        }
        setHealthError(health.error ?? "Cannot connect to PowerDNS")
        return
      }

      // Reachable but has an error (e.g. invalid server_id) → show settings
      if (health.error) {
        setHealthStatus("unreachable")
        setHealthError(health.error)
        return
      }

      if (!health.zone_exists) {
        setHealthStatus("zone_missing")
        return
      }

      setHealthStatus("ready")
      await loadRecords()
    } catch (err) {
      setHealthStatus("unreachable")
      setHealthError(err instanceof Error ? err.message : "Health check failed")
    }
  }, [loadRecords])

  useEffect(() => {
    runHealthCheck()
  }, [runHealthCheck])

  const refreshRecords = useCallback(async () => {
    await runHealthCheck()
  }, [runHealthCheck])

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
      records, zone, isLoading, error,
      healthStatus, healthError,
      refreshRecords,
      handleCreateZone, creatingZone,
    }}>
      {children}
    </DnsZoneContext>
  )
}

export const useDnsZone = () => {
  const ctx = React.useContext(DnsZoneContext)
  if (!ctx) {
    throw new Error("useDnsZone must be used within <DnsZoneProvider>")
  }
  return ctx
}
