"use client"

import { ServersRegisterDialog } from "./servers-register-dialog"
import { ServersUnregisterDialog } from "./servers-unregister-dialog"
import { ServersTable } from "./servers-table"
import { useServers } from "./servers-provider"

export function ServersTableWrapper() {
  const { servers, isLoading, open, setOpen, currentRow, selectedServers } = useServers()

  return (
    <>
      <ServersTable data={servers} isLoading={isLoading} />
      <ServersRegisterDialog
        open={open === "register"}
        onOpenChange={(v) => setOpen(v ? "register" : null)}
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
