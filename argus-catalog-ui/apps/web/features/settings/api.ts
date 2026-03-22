const BASE = "/api/v1/settings"

export type ObjectStorageConfig = {
  endpoint: string
  access_key: string
  secret_key: string
  region: string
  use_ssl: boolean
  bucket: string
  presigned_url_expiry: number
}

export async function fetchObjectStorageConfig(): Promise<ObjectStorageConfig> {
  const res = await fetch(`${BASE}/object-storage`)
  if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`)
  return res.json()
}

export async function updateObjectStorageConfig(
  config: ObjectStorageConfig,
): Promise<void> {
  const res = await fetch(`${BASE}/object-storage`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to update config: ${res.status}`)
}

export async function testObjectStorage(
  endpoint: string,
  accessKey: string,
  secretKey: string,
  region: string,
  bucket: string,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE}/object-storage/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint,
      access_key: accessKey,
      secret_key: secretKey,
      region,
      bucket,
    }),
  })
  if (!res.ok) throw new Error(`Test failed: ${res.status}`)
  return res.json()
}

