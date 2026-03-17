/** Format bytes to human-readable string. */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const units = ["B", "KB", "MB", "GB", "TB", "PB"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, i)
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** Format an ISO date string to a locale-friendly display. */
export function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

/** Extract the display name from a full S3 key. */
export function getNameFromKey(key: string): string {
  const trimmed = key.endsWith("/") ? key.slice(0, -1) : key
  const parts = trimmed.split("/")
  return parts[parts.length - 1] || key
}

/**
 * Build a unique identifier for a storage entry.
 * Folder and object with the same name can coexist in object storage,
 * so we prefix the kind to guarantee uniqueness.
 */
export function entryId(kind: "folder" | "object", key: string): string {
  return `${kind}:${key}`
}

/** Get the file extension from a filename. */
export function getExtension(name: string): string {
  const i = name.lastIndexOf(".")
  return i > 0 ? name.slice(i + 1).toLowerCase() : ""
}

/** Get a category for an extension (for icon mapping). */
export function getFileCategory(
  name: string,
): "image" | "video" | "audio" | "archive" | "code" | "document" | "text" | "data" | "generic" {
  const ext = getExtension(name)
  if (["jpg", "jpeg", "png", "gif", "svg", "webp", "bmp", "ico", "tiff"].includes(ext)) return "image"
  if (["mp4", "avi", "mov", "mkv", "webm", "flv"].includes(ext)) return "video"
  if (["mp3", "wav", "ogg", "flac", "aac", "wma"].includes(ext)) return "audio"
  if (["zip", "tar", "gz", "bz2", "7z", "rar", "xz"].includes(ext)) return "archive"
  if (["js", "ts", "tsx", "jsx", "py", "java", "go", "rs", "c", "cpp", "h", "rb", "sh"].includes(ext)) return "code"
  if (["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "hwp"].includes(ext)) return "document"
  if (["txt", "md", "rst", "log"].includes(ext)) return "text"
  if (["json", "xml", "yaml", "yml", "csv", "tsv", "parquet", "avro"].includes(ext)) return "data"
  return "generic"
}
