/**
 * Kubernetes API client for the dashboard.
 */
import { authFetch } from "@/features/auth/auth-fetch"
import type {
  ClusterOverview,
  K8sResourceItem,
  K8sResourceList,
  NamespaceOverview,
  NamespaceResourceUsage,
} from "./types"

const BASE = "/api/v1/k8s"

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`K8s API error (${res.status}): ${body}`)
  }
  return res.json()
}

// ── Overview ────────────────────────────────────────────────────

export async function fetchClusterOverview(): Promise<ClusterOverview> {
  const res = await authFetch(`${BASE}/overview`)
  return handleResponse(res)
}

export async function fetchNamespaceOverview(
  namespace: string,
): Promise<NamespaceOverview> {
  const res = await authFetch(`${BASE}/overview/${encodeURIComponent(namespace)}`)
  return handleResponse(res)
}

export async function fetchNamespaces(): Promise<string[]> {
  const res = await authFetch(`${BASE}/namespaces`)
  const data = await handleResponse<{ namespaces: string[] }>(res)
  return data.namespaces
}

export async function fetchNamespaceUsage(): Promise<NamespaceResourceUsage[]> {
  const res = await authFetch(`${BASE}/namespace-usage`)
  const data = await handleResponse<{ items: NamespaceResourceUsage[] }>(res)
  return data.items
}

// ── Generic Resource CRUD ───────────────────────────────────────

export async function listResources(
  resource: string,
  namespace?: string,
  params?: Record<string, string>,
): Promise<K8sResourceList> {
  const ns = namespace || "_all"
  const searchParams = new URLSearchParams(params)
  const qs = searchParams.toString() ? `?${searchParams.toString()}` : ""
  const res = await authFetch(`${BASE}/${encodeURIComponent(ns)}/${resource}${qs}`)
  return handleResponse(res)
}

export async function getResource(
  resource: string,
  name: string,
  namespace?: string,
): Promise<K8sResourceItem> {
  const ns = namespace || "_cluster"
  const res = await authFetch(
    `${BASE}/${encodeURIComponent(ns)}/${resource}/${encodeURIComponent(name)}`,
  )
  return handleResponse(res)
}

export async function createResource(
  resource: string,
  body: object,
  namespace?: string,
): Promise<K8sResourceItem> {
  const ns = namespace || "_cluster"
  const res = await authFetch(
    `${BASE}/${encodeURIComponent(ns)}/${resource}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  )
  return handleResponse(res)
}

export async function updateResource(
  resource: string,
  name: string,
  body: object,
  namespace?: string,
): Promise<K8sResourceItem> {
  const ns = namespace || "_cluster"
  const res = await authFetch(
    `${BASE}/${encodeURIComponent(ns)}/${resource}/${encodeURIComponent(name)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  )
  return handleResponse(res)
}

export async function deleteResource(
  resource: string,
  name: string,
  namespace?: string,
): Promise<void> {
  const ns = namespace || "_cluster"
  const res = await authFetch(
    `${BASE}/${encodeURIComponent(ns)}/${resource}/${encodeURIComponent(name)}`,
    { method: "DELETE" },
  )
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`Delete failed (${res.status}): ${body}`)
  }
}

export async function scaleResource(
  resource: string,
  name: string,
  namespace: string,
  replicas: number,
): Promise<void> {
  const res = await authFetch(
    `${BASE}/${encodeURIComponent(namespace)}/${resource}/${encodeURIComponent(name)}/scale`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ replicas }),
    },
  )
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`Scale failed (${res.status}): ${body}`)
  }
}

// ── Pod Logs ────────────────────────────────────────────────────

export async function fetchPodLogs(
  name: string,
  namespace: string,
  options?: {
    container?: string
    tailLines?: number
    sinceSeconds?: number
    timestamps?: boolean
  },
): Promise<string[]> {
  const params = new URLSearchParams()
  if (options?.container) params.set("container", options.container)
  if (options?.tailLines) params.set("tailLines", String(options.tailLines))
  if (options?.sinceSeconds) params.set("sinceSeconds", String(options.sinceSeconds))
  if (options?.timestamps !== undefined) params.set("timestamps", String(options.timestamps))

  const qs = params.toString() ? `?${params.toString()}` : ""
  const res = await authFetch(
    `${BASE}/${encodeURIComponent(namespace)}/pods/${encodeURIComponent(name)}/logs${qs}`,
  )
  const data = await handleResponse<{ logs: string[] }>(res)
  return data.logs
}
