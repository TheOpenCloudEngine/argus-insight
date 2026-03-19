/**
 * DNS Zone API client.
 *
 * Communicates with the argus-insight-server DNS endpoints to fetch and
 * update DNS zone records from the configured PowerDNS server.
 *
 * All requests are proxied through the Next.js middleware to the backend
 * server at the configured API_BASE_URL. Error responses from the backend
 * include a `detail` field with a human-readable message, which is extracted
 * and thrown as an Error for the UI to display.
 */

/** Base path for all DNS API endpoints (proxied to the backend server). */
const BASE = "/api/v1/dns"

// --------------------------------------------------------------------------- //
// Types
// --------------------------------------------------------------------------- //

/**
 * A single flattened DNS record row for the data table.
 *
 * The backend flattens PowerDNS RRsets (which group records by name+type)
 * into individual rows so each record can be displayed as its own table row.
 */
export type DnsRecordRow = {
  /** Fully qualified domain name (e.g. "www.example.com.") */
  name: string
  /** DNS record type (e.g. "A", "AAAA", "CNAME", "MX") */
  type: string
  /** Time-to-live in seconds for DNS caching */
  ttl: number
  /** Record data value; format depends on type (e.g. IP address for A records) */
  content: string
  /** Whether this record is disabled in PowerDNS (disabled records are not served) */
  disabled: boolean
  /** Optional comment attached to the RRset containing this record */
  comment: string
}

/**
 * Response from GET /dns/zone/records.
 * Contains the zone name and all DNS records flattened into table rows.
 */
export type DnsZoneTableResponse = {
  /** The domain name of the zone (without trailing dot) */
  zone: string
  /** All DNS records in the zone, flattened from RRsets */
  records: DnsRecordRow[]
}

/**
 * A single DNS record entry used in PATCH payloads.
 * Represents one record within an RRset modification.
 */
export type DnsRecord = {
  /** The record data value */
  content: string
  /** Whether this record should be disabled */
  disabled: boolean
}

/**
 * A single RRset modification for the PATCH /dns/zone/records endpoint.
 *
 * PowerDNS uses RRsets (name + type) as the unit of modification.
 * REPLACE sets the entire RRset to the provided records (idempotent).
 * DELETE removes the entire RRset from the zone.
 */
export type DnsRRsetPatch = {
  /** Fully qualified domain name (must include trailing dot) */
  name: string
  /** DNS record type */
  type: string
  /** Time-to-live in seconds (ignored for DELETE) */
  ttl: number
  /** Operation: "REPLACE" to add/update, "DELETE" to remove */
  changetype: "REPLACE" | "DELETE"
  /** Records to set (empty for DELETE operations) */
  records: DnsRecord[]
}

/**
 * Response from GET /dns/health.
 * Used by the UI to determine the PowerDNS connection state and decide
 * which view to render (settings prompt, zone creation, or records table).
 */
export type DnsHealthResponse = {
  /** Whether the PowerDNS API server is reachable and authenticated */
  reachable: boolean
  /** Whether the configured domain zone exists on the PowerDNS server */
  zone_exists: boolean
  /** The configured domain name (may be empty if not configured) */
  zone: string
  /** Human-readable error message, or null if healthy */
  error: string | null
}

/**
 * Response from POST /dns/zone.
 * Returned after creating a new zone on the PowerDNS server.
 */
export type DnsZoneCreateResponse = {
  /** The domain name of the newly created zone */
  zone: string
  /** Whether the zone was successfully created */
  created: boolean
}

/**
 * A single BIND configuration file returned by the export endpoint.
 */
export type BindConfigFile = {
  /** Filename (e.g. "named.conf.local", "db.example.com") */
  filename: string
  /** Full text content of the configuration file */
  content: string
}

/**
 * Response from GET /dns/zone/bind-config.
 * Contains the generated BIND configuration files for preview and download.
 */
export type BindConfigResponse = {
  /** The domain name of the zone */
  zone: string
  /** List of generated BIND config files (typically 2: named.conf.local + zone data) */
  files: BindConfigFile[]
}

// --------------------------------------------------------------------------- //
// API functions
// --------------------------------------------------------------------------- //

/**
 * Check PowerDNS connectivity and zone existence.
 *
 * Called on page load by DnsZoneProvider to determine the current state
 * of the PowerDNS connection. The response drives the UI state machine
 * (checking -> not_configured | unreachable | zone_missing | ready).
 *
 * @returns Health status including reachability, zone existence, and any error message.
 * @throws Error if the HTTP request itself fails.
 */
export async function checkDnsHealth(): Promise<DnsHealthResponse> {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to check DNS health: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Create the configured domain zone on the PowerDNS server.
 *
 * Called when the health check indicates the zone does not exist.
 * Creates the zone with a default NS record and glue A record.
 *
 * @returns The zone name and creation status.
 * @throws Error if zone creation fails (e.g. zone already exists, connection error).
 */
export async function createZone(): Promise<DnsZoneCreateResponse> {
  const res = await fetch(`${BASE}/zone`, { method: "POST" })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to create zone: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Fetch all DNS records for the configured domain zone.
 *
 * Returns records already flattened from PowerDNS RRsets so each individual
 * record is its own row in the response array.
 *
 * @returns The zone name and array of flattened DNS record rows.
 * @throws Error if the zone does not exist or PowerDNS is unreachable.
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
 * Fetch BIND configuration files for the configured domain zone.
 *
 * Returns the generated file contents as JSON for preview in the UI.
 * The actual ZIP download uses a separate endpoint via direct browser navigation.
 *
 * @returns The zone name and array of generated BIND config files.
 * @throws Error if the zone does not exist or records cannot be fetched.
 */
export async function fetchBindConfig(): Promise<BindConfigResponse> {
  const res = await fetch(`${BASE}/zone/bind-config`)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail ?? `Failed to fetch bind config: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Update DNS records in the configured domain zone.
 *
 * Sends one or more RRset patches to the backend, which forwards them
 * to the PowerDNS PATCH endpoint. Used for adding new records, editing
 * existing ones, toggling enabled/disabled status, and bulk deletion.
 *
 * @param rrsets - Array of RRset modifications to apply atomically.
 * @throws Error if the update fails (e.g. invalid data, connection error).
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
