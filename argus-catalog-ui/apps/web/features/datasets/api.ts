/**
 * Dataset API client.
 */

import type { DatasetDetail, DatasetSummary, Platform } from "./data/schema"

const BASE = "/api/v1/catalog"

type DatasetListParams = {
  search?: string
  platform?: string
  origin?: string
  tag?: string
  status?: string
  page?: number
  pageSize?: number
}

export type PaginatedDatasets = {
  items: DatasetSummary[]
  total: number
  page: number
  page_size: number
}

export async function fetchDatasets(
  params?: DatasetListParams
): Promise<PaginatedDatasets> {
  const query = new URLSearchParams()
  if (params?.search) query.set("search", params.search)
  if (params?.platform) query.set("platform", params.platform)
  if (params?.origin) query.set("origin", params.origin)
  if (params?.tag) query.set("tag", params.tag)
  if (params?.status) query.set("status", params.status)
  query.set("page", String(params?.page ?? 1))
  query.set("page_size", String(params?.pageSize ?? 20))

  const res = await fetch(`${BASE}/datasets?${query.toString()}`)
  if (!res.ok) throw new Error(`Failed to fetch datasets: ${res.status}`)
  return res.json()
}

export async function fetchDataset(id: number): Promise<DatasetDetail> {
  const res = await fetch(`${BASE}/datasets/${id}`)
  if (!res.ok) throw new Error(`Failed to fetch dataset: ${res.status}`)
  return res.json()
}

export async function createDataset(payload: {
  name: string
  platform_id: number
  description?: string
  origin?: string
  qualified_name?: string
  schema_fields?: {
    field_path: string
    field_type: string
    native_type?: string
    description?: string
    nullable?: string
    ordinal?: number
  }[]
  tags?: number[]
  owners?: { owner_name: string; owner_type: string }[]
}): Promise<DatasetDetail> {
  const res = await fetch(`${BASE}/datasets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to create dataset: ${res.status}`)
  }
  return res.json()
}

export async function updateDataset(
  id: number,
  payload: {
    name?: string
    description?: string
    origin?: string
    qualified_name?: string
    status?: string
  }
): Promise<DatasetDetail> {
  const res = await fetch(`${BASE}/datasets/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to update dataset: ${res.status}`)
  return res.json()
}

export async function deleteDataset(id: number): Promise<void> {
  const res = await fetch(`${BASE}/datasets/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete dataset: ${res.status}`)
}

export async function fetchPlatforms(): Promise<Platform[]> {
  const res = await fetch(`${BASE}/platforms`)
  if (!res.ok) throw new Error(`Failed to fetch platforms: ${res.status}`)
  return res.json()
}

export async function addDatasetTag(
  datasetId: number,
  tagId: number
): Promise<void> {
  const res = await fetch(`${BASE}/datasets/${datasetId}/tags/${tagId}`, {
    method: "POST",
  })
  if (!res.ok)
    throw new Error(`Failed to add tag: ${res.status}`)
}

export async function removeDatasetTag(
  datasetId: number,
  tagId: number
): Promise<void> {
  const res = await fetch(`${BASE}/datasets/${datasetId}/tags/${tagId}`, {
    method: "DELETE",
  })
  if (!res.ok)
    throw new Error(`Failed to remove tag: ${res.status}`)
}

export async function addDatasetOwner(
  datasetId: number,
  payload: { owner_name: string; owner_type: string }
): Promise<void> {
  const res = await fetch(`${BASE}/datasets/${datasetId}/owners`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok)
    throw new Error(`Failed to add owner: ${res.status}`)
}

export async function removeDatasetOwner(
  datasetId: number,
  ownerId: number
): Promise<void> {
  const res = await fetch(
    `${BASE}/datasets/${datasetId}/owners/${ownerId}`,
    { method: "DELETE" }
  )
  if (!res.ok)
    throw new Error(`Failed to remove owner: ${res.status}`)
}
