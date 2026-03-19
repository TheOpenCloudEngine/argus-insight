/**
 * DNS Zone Context Provider.
 *
 * Central state management for the Domain Zone feature. This provider wraps
 * the dns-zone page and exposes all shared state through React Context:
 *
 * - **Record data**: All DNS records fetched from PowerDNS via the backend.
 * - **Zone name**: The configured domain name.
 * - **Dialog control**: Which dialog is currently open and which record triggered it.
 * - **Loading/Error**: Fetch status for the zone records.
 */

"use client"

import React, { useCallback, useEffect, useState } from "react"

import useDialogState from "@/hooks/use-dialog-state"
import { fetchZoneRecords } from "../api"
import { type DnsRecord } from "../data/schema"

type DnsZoneDialogType = "add" | "edit" | "delete"

type DnsZoneContextType = {
  open: DnsZoneDialogType | null
  setOpen: (type: DnsZoneDialogType | null) => void
  currentRow: DnsRecord | null
  setCurrentRow: React.Dispatch<React.SetStateAction<DnsRecord | null>>
  records: DnsRecord[]
  zone: string
  isLoading: boolean
  error: string | null
  refreshRecords: () => Promise<void>
}

const DnsZoneContext = React.createContext<DnsZoneContextType | null>(null)

export function DnsZoneProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useDialogState<DnsZoneDialogType>(null)
  const [currentRow, setCurrentRow] = useState<DnsRecord | null>(null)
  const [records, setRecords] = useState<DnsRecord[]>([])
  const [zone, setZone] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  useEffect(() => {
    loadRecords()
  }, [loadRecords])

  const refreshRecords = useCallback(async () => {
    await loadRecords()
  }, [loadRecords])

  return (
    <DnsZoneContext value={{
      open, setOpen,
      currentRow, setCurrentRow,
      records, zone, isLoading, error,
      refreshRecords,
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
