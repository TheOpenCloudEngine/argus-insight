/**
 * Formatting utilities for K8s resource display.
 */

/**
 * Format a timestamp into a human-readable "age" string.
 * e.g., "5m", "2h", "3d", "12d"
 */
export function formatAge(timestamp: string | null | undefined): string {
  if (!timestamp) return ""
  const now = Date.now()
  const then = new Date(timestamp).getTime()
  if (isNaN(then)) return ""
  const diff = now - then
  if (diff < 0) return "0s"

  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s`

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`

  const days = Math.floor(hours / 24)
  if (days < 365) return `${days}d`

  const years = Math.floor(days / 365)
  return `${years}y`
}

/**
 * Get status color class based on status string.
 */
export function getStatusColor(status: string): string {
  const s = status.toLowerCase()
  // Positive states
  if (
    s === "running" ||
    s === "ready" ||
    s === "active" ||
    s === "bound" ||
    s === "complete" ||
    s === "succeeded" ||
    s === "available" ||
    s === "normal"
  ) {
    return "text-green-600 dark:text-green-400"
  }
  // Warning states
  if (
    s === "pending" ||
    s === "waiting" ||
    s === "warning" ||
    s === "progressing" ||
    s === "containercreating"
  ) {
    return "text-amber-600 dark:text-amber-400"
  }
  // Error states
  if (
    s === "failed" ||
    s === "error" ||
    s === "crashloopbackoff" ||
    s === "imagepullbackoff" ||
    s === "notready" ||
    s === "terminated" ||
    s === "evicted" ||
    s === "oomkilled"
  ) {
    return "text-red-600 dark:text-red-400"
  }
  // Info / neutral
  return "text-muted-foreground"
}

/**
 * Get status badge background class.
 */
export function getStatusBgColor(status: string): string {
  const s = status.toLowerCase()
  if (
    s === "running" || s === "ready" || s === "active" || s === "bound" ||
    s === "complete" || s === "succeeded" || s === "normal"
  ) {
    return "bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20"
  }
  if (
    s === "pending" || s === "waiting" || s === "warning" ||
    s === "progressing" || s === "containercreating"
  ) {
    return "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
  }
  if (
    s === "failed" || s === "error" || s === "crashloopbackoff" ||
    s === "imagepullbackoff" || s === "notready" || s === "evicted"
  ) {
    return "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
  }
  return "bg-muted text-muted-foreground border-border"
}

/**
 * Get a dot color for status indicators.
 */
export function getStatusDotColor(status: string): string {
  const s = status.toLowerCase()
  if (
    s === "running" || s === "ready" || s === "active" || s === "bound" ||
    s === "complete" || s === "succeeded" || s === "normal"
  ) {
    return "bg-green-500"
  }
  if (
    s === "pending" || s === "waiting" || s === "warning" || s === "progressing"
  ) {
    return "bg-amber-500"
  }
  if (
    s === "failed" || s === "error" || s === "crashloopbackoff" || s === "notready"
  ) {
    return "bg-red-500"
  }
  return "bg-gray-400"
}

/**
 * Format bytes to human-readable size.
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const units = ["B", "Ki", "Mi", "Gi", "Ti"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

/**
 * Format K8s quantity strings (e.g., "100m", "1Gi", "500Mi") to readable form.
 */
export function formatQuantity(quantity: string | undefined): string {
  if (!quantity) return ""
  return quantity
}

/**
 * Get nested value from an object using dot-notation path.
 */
export function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce((acc: unknown, key: string) => {
    if (acc === null || acc === undefined) return undefined
    return (acc as Record<string, unknown>)[key]
  }, obj)
}
