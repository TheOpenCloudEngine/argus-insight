import type { GlossaryTerm } from "@/features/datasets/data/schema"

const BASE = "/api/v1/catalog"

export async function fetchGlossaryTerms(): Promise<GlossaryTerm[]> {
  const res = await fetch(`${BASE}/glossary`)
  if (!res.ok) throw new Error(`Failed to fetch glossary terms: ${res.status}`)
  return res.json()
}

export async function createGlossaryTerm(payload: {
  name: string
  description?: string
  source?: string
  parent_id?: number
}): Promise<GlossaryTerm> {
  const res = await fetch(`${BASE}/glossary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to create term: ${res.status}`)
  }
  return res.json()
}

export async function deleteGlossaryTerm(termId: number): Promise<void> {
  const res = await fetch(`${BASE}/glossary/${termId}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete term: ${res.status}`)
}
