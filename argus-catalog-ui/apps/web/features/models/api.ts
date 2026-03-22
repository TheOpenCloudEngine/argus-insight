/**
 * ML Model Registry API client.
 */

import type { ModelSummary } from "./data/schema"

const BASE = "/api/v1/models"

type ModelListParams = {
  search?: string
  status?: string
  python_version?: string
  sklearn_version?: string
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
  if (params?.status) query.set("status", params.status)
  if (params?.python_version) query.set("python_version", params.python_version)
  if (params?.sklearn_version) query.set("sklearn_version", params.sklearn_version)
  query.set("page", String(params?.page ?? 1))
  query.set("page_size", String(params?.pageSize ?? 20))

  const res = await fetch(`${BASE}?${query.toString()}`)
  if (!res.ok) throw new Error(`Failed to fetch models: ${res.status}`)
  return res.json()
}

export type ModelStats = {
  total_models: number
  total_versions: number
  ready_models: number
  ready_versions: number
  pending_count: number
  failed_count: number
  total_access: number
  status_distribution: { status: string; count: number }[]
  model_sizes: { model_name: string; model_size_bytes: number }[]
  versions_per_model: { model_name: string; version_count: number }[]
  daily_access_1d: { date: string; count: number }[]
  daily_access_7d: { date: string; count: number }[]
  daily_access_30d: { date: string; count: number }[]
  access_by_model: Record<string, number>
  total_publish: number
  daily_publish_1d: { date: string; count: number }[]
  daily_publish_7d: { date: string; count: number }[]
  daily_publish_30d: { date: string; count: number }[]
}

export async function fetchModelStats(): Promise<ModelStats> {
  const res = await fetch(`${BASE}/stats`)
  if (!res.ok) throw new Error(`Failed to fetch stats: ${res.status}`)
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
