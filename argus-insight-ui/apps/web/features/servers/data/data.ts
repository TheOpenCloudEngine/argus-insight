import { type ServerStatus } from "./schema"

export const serverStatusStyles = new Map<ServerStatus, string>([
  [
    "REGISTERED",
    "bg-green-500/10 text-green-600 border-green-500/30",
  ],
  [
    "UNREGISTERED",
    "bg-yellow-500/10 text-yellow-600 border-yellow-500/30",
  ],
  [
    "DISCONNECTED",
    "bg-destructive/10 dark:bg-destructive/50 text-destructive dark:text-primary border-destructive/10",
  ],
])
