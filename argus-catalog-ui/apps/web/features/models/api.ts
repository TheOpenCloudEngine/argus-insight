/**
 * ML Model Registry API client.
 */

import type { ModelSummary } from "./data/schema"

const BASE = "/api/v1/models"

type ModelListParams = {
  search?: string
  page?: number
  pageSize?: number
}

export type PaginatedModels = {
  items: ModelSummary[]
  total: number
  page: number
  page_size: number
}

export async function fetchModels(
  params?: ModelListParams,
): Promise<PaginatedModels> {
  const query = new URLSearchParams()
  if (params?.search) query.set("search", params.search)
  query.set("page", String(params?.page ?? 1))
  query.set("page_size", String(params?.pageSize ?? 20))

  const res = await fetch(`${BASE}?${query.toString()}`)
  if (!res.ok) throw new Error(`Failed to fetch models: ${res.status}`)
  return res.json()
}

export async function createModel(payload: {
  name: string
  description?: string
  owner?: string
}): Promise<ModelSummary> {
  const res = await fetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to create model: ${res.status}`)
  }
  return res.json()
}

export async function deleteModel(name: string): Promise<void> {
  const res = await fetch(`${BASE}/${encodeURIComponent(name)}`, {
    method: "DELETE",
  })
  if (!res.ok) throw new Error(`Failed to delete model: ${res.status}`)
}

export async function hardDeleteModels(
  names: string[],
): Promise<{ deleted: string[]; not_found: string[] }> {
  const res = await fetch(`${BASE}/hard-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ names }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to delete models: ${res.status}`)
  }
  return res.json()
}
