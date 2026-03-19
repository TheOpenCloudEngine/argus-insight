import { z } from "zod"

export const dnsRecordSchema = z.object({
  name: z.string(),
  type: z.string(),
  ttl: z.number(),
  content: z.string(),
  disabled: z.boolean(),
  comment: z.string(),
})

export type DnsRecord = z.infer<typeof dnsRecordSchema>
