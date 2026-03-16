import { z } from "zod"

const serverStatusSchema = z.union([
  z.literal("REGISTERED"),
  z.literal("UNREGISTERED"),
  z.literal("DISCONNECTED"),
])
export type ServerStatus = z.infer<typeof serverStatusSchema>

const serverSchema = z.object({
  hostname: z.string(),
  ipAddress: z.string(),
  version: z.string().nullable(),
  osVersion: z.string().nullable(),
  coreCount: z.number().nullable(),
  totalMemory: z.number().nullable(),
  cpuUsage: z.number().nullable(),
  memoryUsage: z.number().nullable(),
  status: serverStatusSchema,
  createdAt: z.coerce.date(),
  updatedAt: z.coerce.date(),
})
export type Server = z.infer<typeof serverSchema>

export const serverListSchema = z.array(serverSchema)
