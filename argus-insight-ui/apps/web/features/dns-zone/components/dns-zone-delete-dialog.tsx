/**
 * DNS Zone Delete Confirmation Dialog.
 *
 * Used for both single-record deletion (from the row action menu) and
 * bulk deletion (from the toolbar Delete Records button). The dialog
 * shows a confirmation message with the count of selected records.
 *
 * The deletion logic groups the selected records by name+type into
 * unique RRsets, then sends DELETE patches for each group. This is
 * necessary because PowerDNS deletes at the RRset level (all records
 * sharing the same name and type are removed together).
 *
 * Uses AlertDialog (not Dialog) for destructive confirmation UX,
 * which requires explicit user action and cannot be dismissed by
 * clicking outside.
 */

"use client"

import { useState } from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { updateZoneRecords } from "../api"
import { type DnsRecord } from "../data/schema"
import { useDnsZone } from "./dns-zone-provider"

/** Props for the DnsZoneDeleteDialog component. */
type DnsZoneDeleteDialogProps = {
  /** Whether the dialog is open */
  open: boolean
  /** Callback to open/close the dialog */
  onOpenChange: (open: boolean) => void
  /** Records to delete (single record for row action, multiple for bulk delete) */
  records: DnsRecord[]
}

/**
 * Confirmation dialog for deleting DNS records.
 *
 * Groups the provided records into unique RRsets (by name+type) and sends
 * DELETE patches for each group. This is because PowerDNS operates at the
 * RRset level -- you cannot delete a single record from a multi-record RRset
 * via a DELETE changetype; the entire RRset is removed.
 */
export function DnsZoneDeleteDialog({ open, onOpenChange, records }: DnsZoneDeleteDialogProps) {
  const { refreshRecords } = useDnsZone()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /**
   * Handle the delete confirmation.
   * Groups records by name+type to deduplicate RRsets, then sends
   * DELETE patches for each unique RRset to the PowerDNS API.
   */
  async function handleDelete() {
    setDeleting(true)
    setError(null)
    try {
      // Group records by name+type to build unique RRset delete patches.
      // Multiple individual records may belong to the same RRset, so we
      // deduplicate to avoid sending redundant DELETE requests.
      const rrsetMap = new Map<string, { name: string; type: string }>()
      for (const record of records) {
        const key = `${record.name}::${record.type}`
        if (!rrsetMap.has(key)) {
          rrsetMap.set(key, { name: record.name, type: record.type })
        }
      }

      const rrsets = Array.from(rrsetMap.values()).map((r) => ({
        name: r.name,
        type: r.type,
        ttl: 0,
        changetype: "DELETE" as const,
        records: [],
      }))

      await updateZoneRecords(rrsets)
      onOpenChange(false)
      await refreshRecords()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete records")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Records</AlertDialogTitle>
          <AlertDialogDescription>
            You have selected {records.length} record(s). Are you sure you want to delete them?
            This action cannot be undone. You will need to re-enter the records manually.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error && (
          <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}
        <AlertDialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
            OK
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
