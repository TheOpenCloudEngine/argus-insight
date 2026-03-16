"use client"

import { ServersTable } from "./servers-table"
import { useServers } from "./servers-provider"

export function ServersTableWrapper() {
  const { servers, isLoading } = useServers()

  return <ServersTable data={servers} isLoading={isLoading} />
}
