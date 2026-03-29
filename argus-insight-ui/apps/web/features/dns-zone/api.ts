/**
 * DNS Zone API client.
 *
 * Communicates with the argus-insight-server DNS endpoints to fetch and
 * update DNS zone records from the configured PowerDNS server.
 */

import { authFetch } from "@/features/auth/auth-fetch"

const BASE = "/api/v1/dns"

// --------------------------------------------------------------------------- //
// Types
// --------------------------------------------------------------------------- //

export type DnsRecordRow = {
  name: string
  type: string
  ttl: number
  content: string
  disabled: boolean
  comment: string
}

export type DnsZoneTableResponse = {
  zone: string
  records: DnsRecordRow[]
}

export type DnsRecord = {
  content: string
  disabled: boolean
}

export type DnsRRsetPatch = {
  name: string
  type: string
  ttl: number
  changetype: "REPLACE" | "DELETE"
  records: DnsRecord[]
}

export type DnsHealthResponse = {
  reachable: boolean
  zone_exists: boolean
  zone: string
  error: string | null
}

export type DnsZoneCreateResponse = {
  zone: string
  created: boolean
}

export type BindConfigFile = {
  filename: string
  content: string
}

export type BindConfigResponse = {
  zone: string
  files: BindConfigFile[]
}

// --------------------------------------------------------------------------- //
// API functions
// --------------------------------------------------------------------------- //

/**
 * Check PowerDNS connectivity and zone existence.
 */
export async function checkDnsHealth(): Promise<DnsHealthResponse> {
  const res = await authFetch(`${BASE}/health`)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to check DNS health: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Create the configured domain zone on the PowerDNS server.
 */
export async function createZone(): Promise<DnsZoneCreateResponse> {
  const res = await authFetch(`${BASE}/zone`, { method: "POST" })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to create zone: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Fetch all DNS records for the configured domain zone.
 */
export async function fetchZoneRecords(): Promise<DnsZoneTableResponse> {
  const res = await authFetch(`${BASE}/zone/records`)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to fetch zone records: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Fetch BIND configuration files for the configured domain zone.
 */
export async function fetchBindConfig(): Promise<BindConfigResponse> {
  const res = await authFetch(`${BASE}/zone/bind-config`)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to fetch bind config: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Update DNS records in the configured domain zone.
 */
export async function updateZoneRecords(rrsets: DnsRRsetPatch[]): Promise<void> {
  const res = await authFetch(`${BASE}/zone/records`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rrsets }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to update zone records: ${res.status}`
    throw new Error(detail)
  }
}
