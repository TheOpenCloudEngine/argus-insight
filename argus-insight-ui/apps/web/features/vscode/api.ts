const BASE = "/api/v1/apps/vscode"

export type VscodeStatus = {
  exists: boolean
  status: string | null
  hostname: string | null
  url: string | null
  createdAt: Date | null
  updatedAt: Date | null
}

export type VscodeLaunchResult = {
  status: string
  hostname: string
  url: string
  message: string
}

export type VscodeDestroyResult = {
  status: string
  message: string
}

function mapStatus(data: Record<string, unknown>): VscodeStatus {
  return {
    exists: data.exists as boolean,
    status: (data.status as string) ?? null,
    hostname: (data.hostname as string) ?? null,
    url: (data.url as string) ?? null,
    createdAt: data.created_at ? new Date(data.created_at as string) : null,
    updatedAt: data.updated_at ? new Date(data.updated_at as string) : null,
  }
}

export async function fetchVscodeStatus(): Promise<VscodeStatus> {
  const res = await fetch(`${BASE}/status`)
  if (!res.ok) throw new Error(`Failed to fetch VS Code status: ${res.status}`)
  return mapStatus(await res.json())
}

export async function launchVscode(): Promise<VscodeLaunchResult> {
  const res = await fetch(`${BASE}/launch`, { method: "POST" })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to launch VS Code: ${res.status}`)
  }
  return res.json()
}

export async function destroyVscode(): Promise<VscodeDestroyResult> {
  const res = await fetch(`${BASE}/destroy`, { method: "DELETE" })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to destroy VS Code: ${res.status}`)
  }
  return res.json()
}

export function getAuthCookieUrl(): string {
  return `${BASE}/auth-cookie`
}
