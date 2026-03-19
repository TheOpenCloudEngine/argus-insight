/**
 * Static data constants for the DNS Zone feature.
 *
 * Contains the reference data used by the DNS zone data table, filters,
 * and dialogs. These constants define the supported record types, status
 * values, and their visual styling.
 */

/**
 * Supported DNS record types for filtering and the "Add Record" dropdown.
 * Each entry provides a label (display text) and value (filter/API value).
 * SOA is included for filtering but excluded from the "Add Record" menu
 * since SOA records are managed automatically by PowerDNS.
 */
export const recordTypes = [
  { label: "A", value: "A" },           // IPv4 address mapping
  { label: "AAAA", value: "AAAA" },     // IPv6 address mapping
  { label: "CNAME", value: "CNAME" },   // Canonical name alias
  { label: "MX", value: "MX" },         // Mail exchange server
  { label: "TXT", value: "TXT" },       // Arbitrary text (SPF, DKIM, etc.)
  { label: "NS", value: "NS" },         // Nameserver delegation
  { label: "SOA", value: "SOA" },       // Start of Authority (auto-managed)
  { label: "PTR", value: "PTR" },       // Reverse DNS pointer
  { label: "SRV", value: "SRV" },       // Service locator
] as const

/**
 * Record status options for the status faceted filter in the toolbar.
 * Maps the boolean `disabled` field to human-readable status labels.
 */
export const recordStatuses = [
  { label: "Enabled", value: "enabled" },   // disabled === false
  { label: "Disabled", value: "disabled" }, // disabled === true
] as const

/**
 * Tailwind CSS class mappings for status badge styling.
 * Uses semantic colors: primary (green tones) for enabled, destructive (red) for disabled.
 */
export const statusStyles = new Map<string, string>([
  ["enabled", "bg-primary/10 text-primary border-primary/30"],
  ["disabled", "bg-destructive/10 text-destructive border-destructive/10"],
])

/**
 * Human-readable descriptions for each DNS record type.
 * Displayed as tooltips in the "Add Record" dropdown menu to help users
 * understand what each record type is used for.
 */
export const recordTypeDescriptions: Record<string, string> = {
  A: "Maps a domain name to an IPv4 address",
  AAAA: "Maps a domain name to an IPv6 address",
  CNAME: "Creates an alias pointing to another domain name",
  MX: "Specifies the mail server for accepting email",
  TXT: "Holds arbitrary text data (SPF, DKIM, etc.)",
  NS: "Delegates a DNS zone to an authoritative name server",
  PTR: "Maps an IP address back to a domain name (reverse DNS)",
  SRV: "Specifies the location of a service (host, port, priority)",
}
