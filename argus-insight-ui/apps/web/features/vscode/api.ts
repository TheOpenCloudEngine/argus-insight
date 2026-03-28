import { authFetch } from "@/features/auth/auth-fetch"

const BASE = "/api/v1/apps/instances/vscode"

export type DeployStep = {
  step: string
  status: "running" | "completed" | "failed"
  message: string
}

export type VscodeStatus = {
  exists: boolean
  status: string | null
  hostname: string | null
  url: string | null
  deploySteps: DeployStep[]
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
  const rawSteps = data.deploy_steps as Array<Record<string, string>> | undefined
  return {
    exists: data.exists as boolean,
    status: (data.status as string) ?? null,
    hostname: (data.hostname as string) ?? null,
    url: (data.url as string) ?? null,
    deploySteps: (rawSteps ?? []).map((s) => ({
      step: s.step,
      status: s.status as DeployStep["status"],
      message: s.message ?? "",
    })),
    createdAt: data.created_at ? new Date(data.created_at as string) : null,
    updatedAt: data.updated_at ? new Date(data.updated_at as string) : null,
  }
}

export async function fetchVscodeStatus(): Promise<VscodeStatus> {
  const res = await authFetch(`${BASE}/status`)
  if (!res.ok) throw new Error(`Failed to fetch VS Code status: ${res.status}`)
  return mapStatus(await res.json())
}

export async function launchVscode(): Promise<VscodeLaunchResult> {
  const res = await authFetch(`${BASE}/launch`, { method: "POST" })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to launch VS Code: ${res.status}`)
  }
  return res.json()
}

export async function destroyVscode(): Promise<VscodeDestroyResult> {
  const res = await authFetch(`${BASE}/destroy`, { method: "DELETE" })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to destroy VS Code: ${res.status}`)
  }
  return res.json()
}

/**
 * Get a launch URL that opens the app directly via the backend server.
 * The backend sets the auth cookie and redirects to the app.
 *
 * @param backendBaseUrl - The backend server URL (e.g. http://10.0.1.50:4500)
 */
export async function getAuthLaunchUrl(backendBaseUrl: string): Promise<string> {
  const res = await authFetch(`${BASE}/auth-launch`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to get launch token: ${res.status}`)
  }
  const { token } = await res.json()
  return `${backendBaseUrl}/api/v1/apps/instances/vscode/auth-redirect?token=${encodeURIComponent(token)}`
}
