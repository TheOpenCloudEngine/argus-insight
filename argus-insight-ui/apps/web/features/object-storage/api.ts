import type { ListObjectsResponse } from "@/components/object-storage-browser"

const BASE = "/api/v1/objectfilemgr"

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

  const res = await fetch(`${BASE}/objects?${params.toString()}`)
  if (!res.ok) throw new Error(`Failed to list objects: ${res.status}`)
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

  const res = await fetch(`${BASE}/objects/delete?${params.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keys }),
  })
  if (!res.ok) throw new Error(`Failed to delete objects: ${res.status}`)
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

  const res = await fetch(`${BASE}/folders?${params.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  })
  if (!res.ok) throw new Error(`Failed to create folder: ${res.status}`)
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

    const res = await fetch(
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
 * Get a presigned download URL for a given key.
 */
export async function getDownloadUrl(
  bucket: string,
  key: string,
): Promise<string> {
  const params = new URLSearchParams()
  params.set("bucket", bucket)
  params.set("key", key)

  const res = await fetch(`${BASE}/objects/download-url?${params.toString()}`)
  if (!res.ok) throw new Error(`Failed to get download URL: ${res.status}`)
  const data = await res.json()
  return data.url
}
