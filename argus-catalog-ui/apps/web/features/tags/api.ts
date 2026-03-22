import type { DatasetSummary, Tag } from "@/features/datasets/data/schema"
import { authFetch } from "@/features/auth/auth-fetch" // Added for SSO AUTH

export type TagUsage = {
  tag: Tag
  datasets: DatasetSummary[]
  total_datasets: number
}

const BASE = "/api/v1/catalog"

export async function fetchTags(): Promise<Tag[]> {
  const res = await authFetch(`${BASE}/tags`)
  if (!res.ok) throw new Error(`Failed to fetch tags: ${res.status}`)
  return res.json()
}

export async function createTag(payload: {
  name: string
  description?: string
  color?: string
}): Promise<Tag> {
  const res = await authFetch(`${BASE}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to create tag: ${res.status}`)
  }
  return res.json()
}

export async function fetchTagUsage(tagId: number): Promise<TagUsage> {
  const res = await authFetch(`${BASE}/tags/${tagId}/usage`)
  if (!res.ok) throw new Error(`Failed to fetch tag usage: ${res.status}`)
  return res.json()
}

export async function deleteTag(tagId: number): Promise<void> {
  const res = await authFetch(`${BASE}/tags/${tagId}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete tag: ${res.status}`)
}
