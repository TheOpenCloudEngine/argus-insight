export function formatTimestamp(ts: number | null | undefined): string {
  if (ts == null) return "—"
  const date = new Date(ts)
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}
