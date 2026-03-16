import { type Server } from "./data/schema"

const BASE = "/api/v1/servermgr"

type ServerListParams = {
  status?: string[]
  search?: string
  page?: number
  pageSize?: number
}

export type PaginatedServers = {
  items: Server[]
  total: number
  page: number
  pageSize: number
}

function mapServer(s: Record<string, unknown>): Server {
  return {
    hostname: String(s.hostname),
    ipAddress: String(s.ip_address),
    version: s.version as string | null,
    osVersion: s.os_version as string | null,
    coreCount: s.core_count as number | null,
    totalMemory: s.total_memory as number | null,
    cpuUsage: s.cpu_usage as number | null,
    memoryUsage: s.memory_usage as number | null,
    status: s.status as Server["status"],
    createdAt: new Date(s.created_at as string),
    updatedAt: new Date(s.updated_at as string),
  }
}

export async function fetchServers(params?: ServerListParams): Promise<PaginatedServers> {
  const query = new URLSearchParams()
  if (params?.status && params.status.length > 0) query.set("status", params.status.join(","))
  if (params?.search) query.set("search", params.search)
  query.set("page", String(params?.page ?? 1))
  query.set("page_size", String(params?.pageSize ?? 10))

  const url = `${BASE}/servers?${query.toString()}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch servers: ${res.status}`)
  const data = await res.json()
  return {
    items: (data.items as Record<string, unknown>[]).map(mapServer),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  }
}
