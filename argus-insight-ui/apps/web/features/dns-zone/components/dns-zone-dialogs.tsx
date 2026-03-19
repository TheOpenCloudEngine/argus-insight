/**
 * DNS Zone Dialogs Orchestrator component.
 *
 * Centralizes the rendering and state management of all dialogs used
 * on the DNS zone page. Each dialog is conditionally rendered based on
 * the `open` state from the DnsZoneProvider context.
 *
 * This component acts as a single mount point for all dialogs to avoid
 * scattering dialog instances across multiple components. It reads the
 * shared context to determine which dialog should be visible and passes
 * the appropriate props (current record, selected records, record type).
 *
 * Dialog types managed:
 * - **add**: Add new DNS record (type-specific form, keyed by record type)
 * - **edit**: Edit existing record (keyed by name+type+content for fresh form state)
 * - **delete**: Delete single record from row action menu
 * - **bulk-delete**: Delete multiple selected records from toolbar button
 * - **bind-conf**: BIND configuration export sheet panel
 *
 * React keys on Edit/Delete dialogs ensure the form state resets when
 * switching between different records. The setTimeout on close handlers
 * delays clearing currentRow to allow the close animation to complete.
 */

"use client"

import { DnsZoneAddDialog } from "./dns-zone-add-dialog"
import { DnsZoneBindDialog } from "./dns-zone-bind-dialog"
import { DnsZoneDeleteDialog } from "./dns-zone-delete-dialog"
import { DnsZoneEditDialog } from "./dns-zone-edit-dialog"
import { useDnsZone } from "./dns-zone-provider"

/**
 * Renders all DNS zone dialogs in a single location.
 *
 * Must be placed inside a DnsZoneProvider. Each dialog instance is
 * conditionally rendered based on the context's `open` state and
 * the availability of required data (currentRow, selectedRecordType).
 */
export function DnsZoneDialogs() {
  const { open, setOpen, currentRow, setCurrentRow, selectedRecordType, selectedRecords } = useDnsZone()

  return (
    <>
      {/* Add Record dialog: only renders when a record type has been selected from the dropdown */}
      {selectedRecordType && (
        <DnsZoneAddDialog
          key={`add-${selectedRecordType}`}
          open={open === "add"}
          onOpenChange={() => setOpen("add")}
          recordType={selectedRecordType}
        />
      )}

      {/* Edit Record dialog: keyed by record identity to reset form when switching records */}
      {currentRow && (
        <DnsZoneEditDialog
          key={`edit-${currentRow.name}-${currentRow.type}-${currentRow.content}`}
          open={open === "edit"}
          onOpenChange={() => {
            setOpen("edit")
            // Delay clearing currentRow so the dialog close animation completes
            setTimeout(() => setCurrentRow(null), 500)
          }}
          currentRow={currentRow}
        />
      )}

      {/* Single Delete dialog: triggered from the row action dropdown menu */}
      {currentRow && (
        <DnsZoneDeleteDialog
          key={`delete-${currentRow.name}-${currentRow.type}`}
          open={open === "delete"}
          onOpenChange={() => {
            setOpen("delete")
            setTimeout(() => setCurrentRow(null), 500)
          }}
          records={[currentRow]}
        />
      )}

      {/* Bulk Delete dialog: triggered from the toolbar "Delete Records" button */}
      <DnsZoneDeleteDialog
        key="bulk-delete"
        open={open === "bulk-delete"}
        onOpenChange={() => setOpen("bulk-delete")}
        records={selectedRecords}
      />

      {/* BIND Configuration Export sheet: sliding panel for config preview and download */}
      <DnsZoneBindDialog
        open={open === "bind-conf"}
        onOpenChange={() => setOpen("bind-conf")}
      />
    </>
  )
}
