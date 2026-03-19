/**
 * Static data for DNS Zone feature.
 *
 * Record type options for faceted filtering and status badge styles.
 */

export const recordTypes = [
  { label: "A", value: "A" },
  { label: "AAAA", value: "AAAA" },
  { label: "CNAME", value: "CNAME" },
  { label: "MX", value: "MX" },
  { label: "TXT", value: "TXT" },
  { label: "NS", value: "NS" },
  { label: "SOA", value: "SOA" },
  { label: "PTR", value: "PTR" },
  { label: "SRV", value: "SRV" },
] as const

export const recordStatuses = [
  { label: "Enabled", value: "enabled" },
  { label: "Disabled", value: "disabled" },
] as const

/** Badge CSS classes keyed by disabled state. */
export const statusStyles = new Map<string, string>([
  ["enabled", "bg-primary/10 text-primary border-primary/30"],
  ["disabled", "bg-destructive/10 text-destructive border-destructive/10"],
])
