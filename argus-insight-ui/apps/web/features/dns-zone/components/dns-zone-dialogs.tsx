/**
 * DNS Zone Dialogs Orchestrator component.
 *
 * Manages the Add Record dialog based on provider state.
 */

"use client"

import { DnsZoneAddDialog } from "./dns-zone-add-dialog"
import { useDnsZone } from "./dns-zone-provider"

export function DnsZoneDialogs() {
  const { open, setOpen, selectedRecordType } = useDnsZone()

  return (
    <>
      {selectedRecordType && (
        <DnsZoneAddDialog
          key={`add-${selectedRecordType}`}
          open={open === "add"}
          onOpenChange={() => setOpen("add")}
          recordType={selectedRecordType}
        />
      )}
    </>
  )
}
