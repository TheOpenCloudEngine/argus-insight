import { authFetch } from "@/features/auth/auth-fetch"
import type {
  PaginatedAuditLogResponse,
  PaginatedWorkspaceResponse,
  WorkspaceService,
  WorkspaceCredentials,
  WorkspaceMember,
  WorkspacePipeline,
  WorkspaceResponse,
} from "./types"

const BASE = "/api/v1/workspace"

async function extractError(res: Response, fallback: string): Promise<string> {
  if (res.status === 502) return "Server connection failed."
  try {
    const data = await res.json()
    if (data.detail) return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)
  } catch { /* ignore */ }
  return `${fallback}: ${res.status}`
}

export async function fetchWorkspaces(
  page = 1,
  pageSize = 10,
  status?: string,
  search?: string,
): Promise<PaginatedWorkspaceResponse> {
  let url = `${BASE}/workspaces?page=${page}&page_size=${pageSize}`
  if (status) url += `&status=${status}`
  if (search) url += `&search=${encodeURIComponent(search)}`
  const res = await authFetch(url)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch workspaces"))
  return res.json()
}

export async function fetchWorkspace(id: number): Promise<WorkspaceResponse> {
  const res = await authFetch(`${BASE}/workspaces/${id}`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch workspace"))
  return res.json()
}

export async function deleteWorkspace(id: number, force = false): Promise<WorkspaceResponse> {
  const res = await authFetch(`${BASE}/workspaces/${id}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to delete workspace"))
  return res.json()
}

export async function fetchWorkspaceMembers(workspaceId: number): Promise<WorkspaceMember[]> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/members`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch members"))
  return res.json()
}

export async function bulkAddWorkspaceMembers(
  workspaceId: number,
  userIds: number[],
): Promise<WorkspaceMember[]> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/members/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_ids: userIds }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to add members"))
  return res.json()
}

export async function addWorkspaceMember(
  workspaceId: number,
  userId: number,
  role: "WorkspaceAdmin" | "User" = "User",
): Promise<WorkspaceMember> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, role }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to add member"))
  return res.json()
}

export async function removeWorkspaceMember(
  workspaceId: number,
  memberId: number,
): Promise<void> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/members/${memberId}`, {
    method: "DELETE",
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to remove member"))
}

export async function fetchWorkspaceServices(
  workspaceId: number,
): Promise<WorkspaceService[]> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/services`)
  if (!res.ok) return []
  return res.json()
}

export async function deleteWorkspaceService(
  workspaceId: number,
  serviceId: number,
): Promise<void> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/services/${serviceId}`, {
    method: "DELETE",
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to delete service"))
}

export async function fetchWorkspacePipelines(
  workspaceId: number,
): Promise<WorkspacePipeline[]> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/pipelines`)
  if (!res.ok) return []
  return res.json()
}

export async function fetchWorkspaceCredentials(
  workspaceId: number,
): Promise<WorkspaceCredentials | null> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/credentials`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch credentials"))
  return res.json()
}

export async function fetchWorkspaceAuditLogs(
  workspaceId: number,
  page = 1,
  pageSize = 20,
): Promise<PaginatedAuditLogResponse> {
  const res = await authFetch(
    `${BASE}/workspaces/${workspaceId}/audit-logs?page=${page}&page_size=${pageSize}`,
  )
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch audit logs"))
  return res.json()
}

