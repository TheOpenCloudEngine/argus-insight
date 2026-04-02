import { authFetch } from "@/features/auth/auth-fetch"
import type {
  PaginatedVocIssues,
  VocComment,
  VocDashboard,
  VocIssue,
} from "./types"

const BASE = "/api/v1/voc"

async function extractError(res: Response, fallback: string): Promise<string> {
  if (res.status === 502) return "Server connection failed."
  try {
    const data = await res.json()
    if (data.detail) return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)
  } catch { /* ignore */ }
  return `${fallback}: ${res.status}`
}

// ── Issues ────────────────────────────────────────────────

export async function fetchVocIssues(params: {
  page?: number
  page_size?: number
  status?: string
  category?: string
  priority?: string
  workspace_id?: number
  assignee_id?: number
  mine?: boolean
  search?: string
} = {}): Promise<PaginatedVocIssues> {
  const qs = new URLSearchParams()
  if (params.page) qs.set("page", String(params.page))
  if (params.page_size) qs.set("page_size", String(params.page_size))
  if (params.status) qs.set("status", params.status)
  if (params.category) qs.set("category", params.category)
  if (params.priority) qs.set("priority", params.priority)
  if (params.workspace_id) qs.set("workspace_id", String(params.workspace_id))
  if (params.assignee_id) qs.set("assignee_id", String(params.assignee_id))
  if (params.mine) qs.set("mine", "true")
  if (params.search) qs.set("search", params.search)
  const res = await authFetch(`${BASE}/issues?${qs}`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch VOC issues"))
  return res.json()
}

export async function fetchVocIssue(id: number): Promise<VocIssue> {
  const res = await authFetch(`${BASE}/issues/${id}`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch VOC issue"))
  return res.json()
}

export async function createVocIssue(data: {
  title: string
  description: string
  category?: string
  priority?: string
  workspace_id?: number | null
  workspace_name?: string | null
  service_id?: number | null
  service_name?: string | null
  resource_detail?: Record<string, unknown> | null
}): Promise<VocIssue> {
  const res = await authFetch(`${BASE}/issues`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to create VOC issue"))
  return res.json()
}

export async function updateVocIssue(
  id: number,
  data: Record<string, unknown>,
): Promise<VocIssue> {
  const res = await authFetch(`${BASE}/issues/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to update VOC issue"))
  return res.json()
}

export async function deleteVocIssue(id: number): Promise<void> {
  const res = await authFetch(`${BASE}/issues/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(await extractError(res, "Failed to delete VOC issue"))
}

// ── Admin actions ─────────────────────────────────────────

export async function changeVocStatus(id: number, status: string): Promise<VocIssue> {
  const res = await authFetch(`${BASE}/issues/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to change status"))
  return res.json()
}

export async function changeVocAssignee(
  id: number,
  assignee_user_id: number | null,
  assignee_username: string | null,
): Promise<VocIssue> {
  const res = await authFetch(`${BASE}/issues/${id}/assignee`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assignee_user_id, assignee_username }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to change assignee"))
  return res.json()
}

export async function changeVocPriority(id: number, priority: string): Promise<VocIssue> {
  const res = await authFetch(`${BASE}/issues/${id}/priority`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ priority }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to change priority"))
  return res.json()
}

// ── Comments ──────────────────────────────────────────────

export async function fetchVocComments(issueId: number): Promise<VocComment[]> {
  const res = await authFetch(`${BASE}/issues/${issueId}/comments`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch comments"))
  return res.json()
}

export async function createVocComment(
  issueId: number,
  body: string,
  bodyPlain?: string,
  parentId?: number | null,
): Promise<VocComment> {
  const res = await authFetch(`${BASE}/issues/${issueId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body, body_plain: bodyPlain, parent_id: parentId }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to create comment"))
  return res.json()
}

export async function deleteVocComment(issueId: number, commentId: number): Promise<void> {
  const res = await authFetch(`${BASE}/issues/${issueId}/comments/${commentId}`, {
    method: "DELETE",
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to delete comment"))
}

// ── Dashboard ─────────────────────────────────────────────

export async function fetchVocDashboard(): Promise<VocDashboard> {
  const res = await authFetch(`${BASE}/dashboard`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch VOC dashboard"))
  return res.json()
}
