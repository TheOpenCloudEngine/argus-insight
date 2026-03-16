"use client"

import { ServersApproveDialog } from "./servers-approve-dialog"
import { ServersUnregisterDialog } from "./servers-unregister-dialog"
import { ServersTable } from "./servers-table"
import { useServers } from "./servers-provider"

export function ServersTableWrapper() {
  const { servers, isLoading, open, setOpen, currentRow, selectedServers } = useServers()

  return (
    <>
      <ServersTable data={servers} isLoading={isLoading} />
      <ServersApproveDialog
        open={open === "approve"}
        onOpenChange={(v) => setOpen(v ? "approve" : null)}
        currentRow={currentRow}
        selectedServers={selectedServers}
      />
      <ServersUnregisterDialog
        open={open === "unregister"}
        onOpenChange={(v) => setOpen(v ? "unregister" : null)}
        currentRow={currentRow}
        selectedServers={selectedServers}
      />
    </>
  )
}
