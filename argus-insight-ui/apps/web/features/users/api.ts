import { type User } from "./data/schema"

const BASE = "/api/v1/usermgr"

type UserListParams = {
  status?: string
  role?: string
  search?: string
}

export async function fetchUsers(params?: UserListParams): Promise<User[]> {
  const query = new URLSearchParams()
  if (params?.status) query.set("status", params.status)
  if (params?.role) query.set("role", params.role)
  if (params?.search) query.set("search", params.search)

  const qs = query.toString()
  const url = `${BASE}/users${qs ? `?${qs}` : ""}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch users: ${res.status}`)
  const data = await res.json()
  return data.map((u: Record<string, unknown>) => ({
    ...u,
    id: String(u.id),
    firstName: u.first_name,
    lastName: u.last_name,
    phoneNumber: u.phone_number ?? "",
    createdAt: new Date(u.created_at as string),
    updatedAt: new Date(u.updated_at as string),
  }))
}

type CreateUserPayload = {
  username: string
  email: string
  first_name: string
  last_name: string
  phone_number: string
  password: string
  role: "Admin" | "User"
}

export async function createUser(payload: CreateUserPayload): Promise<User> {
  const res = await fetch(`${BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to create user: ${res.status}`)
  }
  return res.json()
}

export async function deleteUser(userId: string): Promise<void> {
  const res = await fetch(`${BASE}/users/${userId}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete user: ${res.status}`)
}

export async function activateUser(userId: string): Promise<void> {
  const res = await fetch(`${BASE}/users/${userId}/activate`, { method: "PUT" })
  if (!res.ok) throw new Error(`Failed to activate user: ${res.status}`)
}

export async function deactivateUser(userId: string): Promise<void> {
  const res = await fetch(`${BASE}/users/${userId}/deactivate`, { method: "PUT" })
  if (!res.ok) throw new Error(`Failed to deactivate user: ${res.status}`)
}

export async function modifyUser(
  userId: string,
  payload: { first_name?: string; last_name?: string; email?: string; phone_number?: string },
): Promise<User> {
  const res = await fetch(`${BASE}/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to modify user: ${res.status}`)
  return res.json()
}
