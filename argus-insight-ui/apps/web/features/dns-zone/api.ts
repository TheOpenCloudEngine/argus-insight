/**
 * DNS Zone API client.
 *
 * Communicates with the argus-insight-server DNS endpoints to fetch and
 * update DNS zone records from the configured PowerDNS server.
 */

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

// --------------------------------------------------------------------------- //
// API functions
// --------------------------------------------------------------------------- //

/**
 * Fetch all DNS records for the configured domain zone.
 */
export async function fetchZoneRecords(): Promise<DnsZoneTableResponse> {
  const res = await fetch(`${BASE}/zone/records`)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to fetch zone records: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Update DNS records in the configured domain zone.
 */
export async function updateZoneRecords(rrsets: DnsRRsetPatch[]): Promise<void> {
  const res = await fetch(`${BASE}/zone/records`, {
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
