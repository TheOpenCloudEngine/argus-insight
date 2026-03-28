/**
 * Notes API client.
 *
 * Provides functions to communicate with the backend notes endpoints
 * (`/api/v1/notes/*`). All requests are proxied through the Next.js middleware.
 */

import { authFetch } from "@/features/auth/auth-fetch"

const BASE = "/api/v1/notes"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Notebook = {
  id: number
  userId: number
  title: string
  description: string | null
  color: string
  isPinned: boolean
  sectionCount: number
  pageCount: number
  createdAt: string
  updatedAt: string
}

export type Section = {
  id: number
  notebookId: number
  title: string
  color: string
  displayOrder: number
  pageCount: number
  createdAt: string
  updatedAt: string
}

export type PageListItem = {
  id: number
  sectionId: number
  title: string
  displayOrder: number
  isPinned: boolean
  createdAt: string
  updatedAt: string
}

export type Page = {
  id: number
  sectionId: number
  title: string
  content: string
  displayOrder: number
  isPinned: boolean
  currentVersion: number
  createdAt: string
  updatedAt: string
}

export type VersionListItem = {
  id: number
  version: number
  title: string
  changeSummary: string | null
  createdAt: string
}

export type Version = {
  id: number
  pageId: number
  version: number
  title: string
  content: string
  changeSummary: string | null
  createdAt: string
}

// ---------------------------------------------------------------------------
// Snake-to-camel mapping helpers
// ---------------------------------------------------------------------------

function mapNotebook(raw: Record<string, unknown>): Notebook {
  return {
    id: raw.id as number,
    userId: raw.user_id as number,
    title: raw.title as string,
    description: (raw.description as string) ?? null,
    color: raw.color as string,
    isPinned: raw.is_pinned as boolean,
    sectionCount: raw.section_count as number,
    pageCount: raw.page_count as number,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  }
}

function mapSection(raw: Record<string, unknown>): Section {
  return {
    id: raw.id as number,
    notebookId: raw.notebook_id as number,
    title: raw.title as string,
    color: raw.color as string,
    displayOrder: raw.display_order as number,
    pageCount: raw.page_count as number,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  }
}

function mapPageListItem(raw: Record<string, unknown>): PageListItem {
  return {
    id: raw.id as number,
    sectionId: raw.section_id as number,
    title: raw.title as string,
    displayOrder: raw.display_order as number,
    isPinned: raw.is_pinned as boolean,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  }
}

function mapPage(raw: Record<string, unknown>): Page {
  return {
    id: raw.id as number,
    sectionId: raw.section_id as number,
    title: raw.title as string,
    content: raw.content as string,
    displayOrder: raw.display_order as number,
    isPinned: raw.is_pinned as boolean,
    currentVersion: raw.current_version as number,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  }
}

function mapVersionListItem(raw: Record<string, unknown>): VersionListItem {
  return {
    id: raw.id as number,
    version: raw.version as number,
    title: raw.title as string,
    changeSummary: (raw.change_summary as string) ?? null,
    createdAt: raw.created_at as string,
  }
}

function mapVersion(raw: Record<string, unknown>): Version {
  return {
    id: raw.id as number,
    pageId: raw.page_id as number,
    version: raw.version as number,
    title: raw.title as string,
    content: raw.content as string,
    changeSummary: (raw.change_summary as string) ?? null,
    createdAt: raw.created_at as string,
  }
}

// ---------------------------------------------------------------------------
// Notebook API
// ---------------------------------------------------------------------------

export async function fetchNotebooks(search?: string): Promise<{ items: Notebook[]; total: number }> {
  const query = new URLSearchParams()
  if (search) query.set("search", search)
  const res = await authFetch(`${BASE}/notebooks?${query.toString()}`)
  if (!res.ok) throw new Error(`Failed to fetch notebooks: ${res.status}`)
  const data = await res.json()
  return {
    items: (data.items as Record<string, unknown>[]).map(mapNotebook),
    total: data.total,
  }
}

export async function fetchNotebook(id: number): Promise<Notebook> {
  const res = await authFetch(`${BASE}/notebooks/${id}`)
  if (!res.ok) throw new Error(`Failed to fetch notebook: ${res.status}`)
  return mapNotebook(await res.json())
}

export async function createNotebook(payload: {
  title: string
  description?: string
  color?: string
}): Promise<Notebook> {
  const res = await authFetch(`${BASE}/notebooks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to create notebook: ${res.status}`)
  return mapNotebook(await res.json())
}

export async function updateNotebook(
  id: number,
  payload: { title?: string; description?: string; color?: string; is_pinned?: boolean },
): Promise<Notebook> {
  const res = await authFetch(`${BASE}/notebooks/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to update notebook: ${res.status}`)
  return mapNotebook(await res.json())
}

export async function deleteNotebook(id: number): Promise<void> {
  const res = await authFetch(`${BASE}/notebooks/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete notebook: ${res.status}`)
}

// ---------------------------------------------------------------------------
// Section API
// ---------------------------------------------------------------------------

export async function fetchSections(notebookId: number): Promise<Section[]> {
  const res = await authFetch(`${BASE}/notebooks/${notebookId}/sections`)
  if (!res.ok) throw new Error(`Failed to fetch sections: ${res.status}`)
  const data = await res.json()
  return (data as Record<string, unknown>[]).map(mapSection)
}

export async function createSection(
  notebookId: number,
  payload: { title: string; color?: string },
): Promise<Section> {
  const res = await authFetch(`${BASE}/notebooks/${notebookId}/sections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to create section: ${res.status}`)
  return mapSection(await res.json())
}

export async function updateSection(
  sectionId: number,
  payload: { title?: string; color?: string },
): Promise<Section> {
  const res = await authFetch(`${BASE}/sections/${sectionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to update section: ${res.status}`)
  return mapSection(await res.json())
}

export async function deleteSection(sectionId: number): Promise<void> {
  const res = await authFetch(`${BASE}/sections/${sectionId}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete section: ${res.status}`)
}

// ---------------------------------------------------------------------------
// Page API
// ---------------------------------------------------------------------------

export async function fetchPages(sectionId: number): Promise<PageListItem[]> {
  const res = await authFetch(`${BASE}/sections/${sectionId}/pages`)
  if (!res.ok) throw new Error(`Failed to fetch pages: ${res.status}`)
  const data = await res.json()
  return (data as Record<string, unknown>[]).map(mapPageListItem)
}

export async function fetchPage(pageId: number): Promise<Page> {
  const res = await authFetch(`${BASE}/pages/${pageId}`)
  if (!res.ok) throw new Error(`Failed to fetch page: ${res.status}`)
  return mapPage(await res.json())
}

export async function createPage(
  sectionId: number,
  payload: { title: string; content?: string },
): Promise<Page> {
  const res = await authFetch(`${BASE}/sections/${sectionId}/pages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to create page: ${res.status}`)
  return mapPage(await res.json())
}

export async function updatePage(
  pageId: number,
  payload: { title?: string; content?: string; is_pinned?: boolean; change_summary?: string },
): Promise<Page> {
  const res = await authFetch(`${BASE}/pages/${pageId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to update page: ${res.status}`)
  return mapPage(await res.json())
}

export async function deletePage(pageId: number): Promise<void> {
  const res = await authFetch(`${BASE}/pages/${pageId}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete page: ${res.status}`)
}

// ---------------------------------------------------------------------------
// Version API
// ---------------------------------------------------------------------------

export async function fetchVersions(pageId: number): Promise<VersionListItem[]> {
  const res = await authFetch(`${BASE}/pages/${pageId}/versions`)
  if (!res.ok) throw new Error(`Failed to fetch versions: ${res.status}`)
  const data = await res.json()
  return (data as Record<string, unknown>[]).map(mapVersionListItem)
}

export async function fetchVersion(pageId: number, version: number): Promise<Version> {
  const res = await authFetch(`${BASE}/pages/${pageId}/versions/${version}`)
  if (!res.ok) throw new Error(`Failed to fetch version: ${res.status}`)
  return mapVersion(await res.json())
}

export async function restoreVersion(pageId: number, version: number): Promise<Page> {
  const res = await authFetch(`${BASE}/pages/${pageId}/versions/${version}/restore`, {
    method: "POST",
  })
  if (!res.ok) throw new Error(`Failed to restore version: ${res.status}`)
  return mapPage(await res.json())
}
