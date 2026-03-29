import { authFetch } from "@/features/auth/auth-fetch"
import type { ListObjectsResponse } from "@/components/object-storage-browser"

const BASE = "/api/v1/objectfilemgr"

// --------------------------------------------------------------------------- //
// Error helpers
// --------------------------------------------------------------------------- //

async function extractErrorMessage(res: Response, fallback: string): Promise<string> {
  if (res.status === 502) {
    return "서버에 연결할 수 없습니다. argus-insight-server가 실행 중인지 확인하세요."
  }
  if (res.status === 503) {
    try {
      const data = await res.json()
      return data.detail || "서비스를 사용할 수 없습니다."
    } catch {
      return "서비스를 사용할 수 없습니다."
    }
  }
  try {
    const data = await res.json()
    if (data.detail) return data.detail
  } catch {
    // ignore parse errors
  }
  return `${fallback}: ${res.status}`
}

// --------------------------------------------------------------------------- //
// File Browser Configuration
// --------------------------------------------------------------------------- //

/** A single preview category with its extensions and limits. */
export type PreviewCategoryConfig = {
  category: string
  label: string
  extensions: string[]
  max_file_size: number
  max_preview_rows: number | null
}

/** Full File Browser configuration from the server. */
export type FilebrowserConfig = {
  browser: Record<string, number>
  preview: PreviewCategoryConfig[]
}

/**
 * Fetch File Browser configuration (browser settings + preview limits).
 * Called once when the File Browser first mounts.
 */
export async function fetchFilebrowserConfig(): Promise<FilebrowserConfig> {
  const res = await authFetch(`${BASE}/configuration`)
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to fetch filebrowser config"))
  return res.json()
}

/**
 * Update browser-level settings (sort_disable_threshold, max_keys_per_page, etc.).
 */
export async function updateBrowserSettings(
  browser: Record<string, number>,
): Promise<void> {
  const res = await authFetch(`${BASE}/configuration/browser`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ browser }),
  })
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to update browser settings"))
}

/**
 * Update a single preview category's limits.
 */
export async function updatePreviewCategory(
  category: string,
  max_file_size: number,
  max_preview_rows: number | null,
): Promise<void> {
  const res = await authFetch(`${BASE}/configuration/preview`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, max_file_size, max_preview_rows }),
  })
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to update preview category"))
}

// --------------------------------------------------------------------------- //
// Bucket Management
// --------------------------------------------------------------------------- //

export type BucketInfo = {
  name: string
  creation_date: string | null
}

export type BucketListResponse = {
  buckets: BucketInfo[]
}

export type EnsureUserBucketsResponse = {
  created: string[]
  existing: string[]
}

/**
 * List all S3 buckets.
 */
export async function listBuckets(): Promise<BucketListResponse> {
  const res = await authFetch(`${BASE}/buckets`)
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to list buckets"))
  return res.json()
}

/**
 * Ensure user-<username> buckets exist for all users.
 */
export async function ensureUserBuckets(): Promise<EnsureUserBucketsResponse> {
  const res = await authFetch(`${BASE}/buckets/ensure-user-buckets`, {
    method: "POST",
  })
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to ensure user buckets"))
  return res.json()
}

// --------------------------------------------------------------------------- //
// Objects
// --------------------------------------------------------------------------- //

/**
 * List objects and folders under a prefix.
 * Maps the server response to the UI's ListObjectsResponse shape.
 */
export async function listObjects(
  bucket: string,
  prefix: string,
  continuationToken?: string,
): Promise<ListObjectsResponse> {
  const params = new URLSearchParams()
  params.set("bucket", bucket)
  params.set("prefix", prefix)
  params.set("delimiter", "/")
  params.set("max_keys", "1000")
  if (continuationToken) {
    params.set("continuation_token", continuationToken)
  }

  const res = await authFetch(`${BASE}/objects?${params.toString()}`)
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to list objects"))
  const data = await res.json()

  return {
    folders: (data.folders ?? []).map(
      (f: { prefix: string; name: string }) => ({
        kind: "folder" as const,
        key: f.prefix,
        name: f.name,
      }),
    ),
    objects: (data.objects ?? []).map(
      (o: {
        key: string
        size: number
        last_modified: string
        storage_class?: string
      }) => ({
        kind: "object" as const,
        key: o.key,
        name: o.key.split("/").filter(Boolean).pop() ?? o.key,
        size: o.size,
        lastModified: o.last_modified,
        storageClass: o.storage_class,
      }),
    ),
    nextContinuationToken: data.next_continuation_token ?? undefined,
    isTruncated: data.is_truncated ?? false,
  }
}

/**
 * Delete one or more objects.
 */
export async function deleteObjects(
  bucket: string,
  keys: string[],
): Promise<void> {
  const params = new URLSearchParams()
  params.set("bucket", bucket)

  const res = await authFetch(`${BASE}/objects/delete?${params.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keys }),
  })
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to delete objects"))
}

/**
 * Create a virtual folder (0-byte object with trailing slash).
 */
export async function createFolder(
  bucket: string,
  key: string,
): Promise<void> {
  const params = new URLSearchParams()
  params.set("bucket", bucket)

  const res = await authFetch(`${BASE}/folders?${params.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  })
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to create folder"))
}

/**
 * Upload files to the given prefix via multipart form data.
 */
export async function uploadFiles(
  bucket: string,
  prefix: string,
  files: File[],
): Promise<void> {
  for (const file of files) {
    const key = prefix + file.name
    const params = new URLSearchParams()
    params.set("bucket", bucket)
    params.set("key", key)

    const formData = new FormData()
    formData.append("file", file)

    const res = await authFetch(
      `${BASE}/objects/upload?${params.toString()}`,
      {
        method: "POST",
        body: formData,
      },
    )
    if (!res.ok) throw new Error(`Failed to upload ${file.name}: ${res.status}`)
  }
}

/**
 * Copy an object to a new key (used for rename/move).
 */
export async function copyObject(
  bucket: string,
  sourceKey: string,
  destinationKey: string,
): Promise<void> {
  const params = new URLSearchParams()
  params.set("bucket", bucket)

  const res = await authFetch(`${BASE}/objects/copy?${params.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_key: sourceKey,
      destination_key: destinationKey,
    }),
  })
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to copy object"))
}

/**
 * Upload a single file with progress tracking via XMLHttpRequest.
 */
export function uploadFileWithProgress(
  bucket: string,
  prefix: string,
  file: File,
  onProgress: (progress: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const key = prefix + file.name
    const params = new URLSearchParams()
    params.set("bucket", bucket)
    params.set("key", key)

    const formData = new FormData()
    formData.append("file", file)

    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${BASE}/objects/upload?${params.toString()}`)

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100)
        resolve()
      } else {
        reject(new Error(`Failed to upload ${file.name}: ${xhr.status}`))
      }
    })

    xhr.addEventListener("error", () => {
      reject(new Error(`Network error uploading ${file.name}`))
    })

    xhr.send(formData)
  })
}

/** Tabular preview response (parquet, xlsx, xls). */
export type TablePreviewResponse = {
  format: string
  columns: string[]
  rows: unknown[][]
  total_rows: number
  sheet_names: string[]
  active_sheet: string
}

/** Document preview response (docx, pptx). */
export type DocumentPreviewResponse = {
  format: string
  html: string
  slides?: { slide_number: number; texts: string[]; notes: string }[] | null
}

/**
 * Request server-side file preview (parquet, xlsx, xls, docx, pptx).
 */
export async function previewFile(
  bucket: string,
  key: string,
  options?: { sheet?: string; maxRows?: number },
): Promise<TablePreviewResponse | DocumentPreviewResponse> {
  const params = new URLSearchParams()
  params.set("bucket", bucket)
  params.set("key", key)
  if (options?.sheet) params.set("sheet", options.sheet)
  if (options?.maxRows) params.set("max_rows", String(options.maxRows))

  const res = await authFetch(`${BASE}/objects/preview?${params.toString()}`)
  if (!res.ok) {
    const detail = await res.text().catch(() => "")
    throw new Error(`Preview failed (${res.status}): ${detail}`)
  }
  return res.json()
}

/**
 * Get a presigned download URL for a given key.
 */
export async function getDownloadUrl(
  bucket: string,
  key: string,
): Promise<string> {
  const params = new URLSearchParams()
  params.set("bucket", bucket)
  params.set("key", key)

  const res = await authFetch(`${BASE}/objects/download-url?${params.toString()}`)
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to get download URL"))
  const data = await res.json()
  return data.url
}
