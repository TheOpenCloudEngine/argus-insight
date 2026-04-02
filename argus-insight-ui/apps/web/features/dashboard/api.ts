import { authFetch } from "@/features/auth/auth-fetch"
import type { AdminDashboard } from "./types"

export async function fetchAdminDashboard(): Promise<AdminDashboard> {
  const res = await authFetch("/api/v1/dashboard/admin-overview")
  if (!res.ok) throw new Error(`Failed to fetch admin dashboard: ${res.status}`)
  return res.json()
}
