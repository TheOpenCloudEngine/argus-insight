import { authFetch } from "@/features/auth/auth-fetch"
import type {
  PaginatedAuditLogResponse,
  PaginatedWorkspaceResponse,
  ResourceProfile,
  ServiceEvent,
  ServiceLogSources,
  ServiceLogs,
  WorkspaceService,
  WorkspaceCredentials,
  WorkspaceMember,
  WorkspacePipeline,
  WorkspaceDashboard,
  WorkspaceResourceUsage,
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

// ── Resource Profiles ──────────────────────────────────────────

const PROFILE_BASE = "/api/v1/resource-profiles"

export async function fetchResourceProfiles(): Promise<ResourceProfile[]> {
  const res = await authFetch(PROFILE_BASE)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch profiles"))
  return res.json()
}

export async function createResourceProfile(data: {
  name: string
  display_name: string
  description?: string
  cpu_cores: number
  memory_gb: number
  is_default?: boolean
}): Promise<ResourceProfile> {
  const res = await authFetch(PROFILE_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to create profile"))
  return res.json()
}

export async function updateResourceProfile(
  id: number,
  data: {
    display_name?: string
    description?: string
    cpu_cores?: number
    memory_gb?: number
    is_default?: boolean
  },
): Promise<ResourceProfile> {
  const res = await authFetch(`${PROFILE_BASE}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to update profile"))
  return res.json()
}

export async function deleteResourceProfile(id: number): Promise<void> {
  const res = await authFetch(`${PROFILE_BASE}/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(await extractError(res, "Failed to delete profile"))
}

export async function assignWorkspaceProfile(
  workspaceId: number,
  profileId: number | null,
): Promise<void> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/resource-profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to assign profile"))
}

export async function fetchWorkspaceResourceUsage(
  workspaceId: number,
): Promise<WorkspaceResourceUsage> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/resource-usage`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch resource usage"))
  return res.json()
}

// ── Service Logs ─────────────────────────────────────────────────

export async function fetchServiceLogSources(
  workspaceId: number,
  serviceId: number,
): Promise<ServiceLogSources> {
  const res = await authFetch(
    `${BASE}/workspaces/${workspaceId}/services/${serviceId}/log-sources`,
  )
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch log sources"))
  return res.json()
}

export async function fetchServiceLogs(
  workspaceId: number,
  serviceId: number,
  opts: {
    container?: string
    tailLines?: number
    sinceSeconds?: number
    timestamps?: boolean
  } = {},
): Promise<ServiceLogs> {
  const params = new URLSearchParams()
  if (opts.container) params.set("container", opts.container)
  if (opts.tailLines) params.set("tailLines", String(opts.tailLines))
  if (opts.sinceSeconds) params.set("sinceSeconds", String(opts.sinceSeconds))
  if (opts.timestamps !== undefined) params.set("timestamps", String(opts.timestamps))
  const qs = params.toString()
  const res = await authFetch(
    `${BASE}/workspaces/${workspaceId}/services/${serviceId}/logs${qs ? `?${qs}` : ""}`,
  )
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch logs"))
  return res.json()
}

export function createServiceLogStream(
  workspaceId: number,
  serviceId: number,
  opts: {
    container?: string
    tailLines?: number
    sinceSeconds?: number
  } = {},
): EventSource {
  const params = new URLSearchParams({ follow: "true" })
  if (opts.container) params.set("container", opts.container)
  if (opts.tailLines) params.set("tailLines", String(opts.tailLines))
  if (opts.sinceSeconds) params.set("sinceSeconds", String(opts.sinceSeconds))
  return new EventSource(
    `${BASE}/workspaces/${workspaceId}/services/${serviceId}/logs?${params}`,
  )
}

export async function fetchServiceEvents(
  workspaceId: number,
  serviceId: number,
): Promise<ServiceEvent[]> {
  const res = await authFetch(
    `${BASE}/workspaces/${workspaceId}/services/${serviceId}/events`,
  )
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch events"))
  return res.json()
}

// ── Workspace Dashboard ──────────────────────────────────

export async function fetchWorkspaceDashboard(
  workspaceId: number,
): Promise<WorkspaceDashboard> {
  const res = await authFetch(`${BASE}/workspaces/${workspaceId}/dashboard`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch dashboard"))
  return res.json()
}

