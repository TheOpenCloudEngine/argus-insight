/**
 * DNS record Zod validation schema.
 *
 * Defines the runtime validation schema for a single DNS record row
 * as returned by the backend API. This schema is used by TanStack Table
 * for type safety and by React Hook Form for form validation.
 *
 * The fields mirror the backend's DnsRecordRow Pydantic model.
 */

import { z } from "zod"

/** Zod schema for validating a single DNS record row from the API. */
export const dnsRecordSchema = z.object({
  /** Fully qualified domain name (e.g. "www.example.com.") */
  name: z.string(),
  /** DNS record type (e.g. "A", "AAAA", "CNAME", "MX", "TXT", "NS") */
  type: z.string(),
  /** Time-to-live in seconds for DNS caching */
  ttl: z.number(),
  /** Record data value; format varies by type (e.g. IP for A, hostname for CNAME) */
  content: z.string(),
  /** Whether this record is disabled (not served by the DNS server) */
  disabled: z.boolean(),
  /** Optional comment attached to the RRset containing this record */
  comment: z.string(),
})

/** TypeScript type inferred from the Zod schema. Used throughout the DNS zone feature. */
export type DnsRecord = z.infer<typeof dnsRecordSchema>
