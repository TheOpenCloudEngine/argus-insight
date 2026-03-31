/**
 * User Management API client.
 *
 * Provides functions to communicate with the backend user management endpoints
 * (`/api/v1/usermgr/*`). All requests are proxied through the Next.js middleware
 * to the argus-insight-server.
 *
 * Key responsibilities:
 * - Fetching paginated user lists with optional filters (status, role, search).
 * - Creating, modifying, and deleting user accounts.
 * - Checking uniqueness of usernames and emails before submission.
 * - Activating and deactivating user accounts.
 * - Converting backend snake_case responses to frontend camelCase via `mapUser()`.
 */

import { authFetch } from "@/features/auth/auth-fetch"
import { type User } from "./data/schema"

/** Base URL prefix for all user management API calls. */
const BASE = "/api/v1/usermgr"

/**
 * Query parameters for the user list endpoint.
 *
 * All fields are optional; when omitted, the backend returns unfiltered results.
 */
type UserListParams = {
  /** Filter by account status ("active" or "inactive"). */
  status?: string
  /** Filter by role name ("Admin" or "User"). */
  role?: string
  /** Free-text search across username, name, email, and phone number. */
  search?: string
  /** Page number (1-based). Defaults to 1. */
  page?: number
  /** Number of items per page. Defaults to 10. */
  pageSize?: number
}

/**
 * Paginated response shape returned by `fetchUsers()`.
 */
export type PaginatedUsers = {
  items: User[]
  total: number
  page: number
  pageSize: number
}

/**
 * Map a raw backend user object (snake_case) to the frontend User type (camelCase).
 *
 * The backend returns fields like `first_name`, `last_name`, `phone_number`, etc.
 * This function normalizes them to the camelCase convention used throughout the UI.
 * The role name is also lowercased to match the frontend enum ("Admin" -> "admin").
 */
function mapUser(u: Record<string, unknown>): User {
  return {
    ...u,
    id: String(u.id),
    firstName: u.first_name,
    lastName: u.last_name,
    phoneNumber: u.phone_number ?? "",
    role: typeof u.role === "string" ? u.role.toLowerCase() : u.role,
    createdAt: new Date(u.created_at as string),
    updatedAt: new Date(u.updated_at as string),
  } as User
}

/**
 * Fetch a paginated list of users from the backend.
 *
 * Constructs query parameters from the provided filters and pagination settings,
 * then sends a GET request to `/api/v1/usermgr/users`. The response items are
 * mapped from snake_case to camelCase before being returned.
 *
 * @param params - Optional filters and pagination settings.
 * @returns Paginated user list with total count.
 * @throws Error if the HTTP response is not OK.
 */
export async function fetchUsers(params?: UserListParams): Promise<PaginatedUsers> {
  const query = new URLSearchParams()
  if (params?.status) query.set("status", params.status)
  if (params?.role) query.set("role", params.role)
  if (params?.search) query.set("search", params.search)
  query.set("page", String(params?.page ?? 1))
  query.set("page_size", String(params?.pageSize ?? 10))

  const url = `${BASE}/users?${query.toString()}`
  const res = await authFetch(url)
  if (!res.ok) throw new Error(`Failed to fetch users: ${res.status}`)
  const data = await res.json()
  return {
    items: (data.items as Record<string, unknown>[]).map(mapUser),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  }
}

/**
 * Check whether a username or email is already taken.
 *
 * Used for real-time validation in the user creation form. When the user tabs
 * out of the username or email field, this function is called to provide
 * immediate feedback if the value conflicts with an existing account.
 *
 * @param params - Object containing the username and/or email to check.
 * @returns Object with boolean flags `username_exists` and/or `email_exists`.
 * @throws Error if the HTTP response is not OK.
 */
export async function checkUserExists(params: {
  username?: string
  email?: string
}): Promise<{ username_exists?: boolean; email_exists?: boolean }> {
  const query = new URLSearchParams()
  if (params.username) query.set("username", params.username)
  if (params.email) query.set("email", params.email)
  const res = await authFetch(`${BASE}/check-user?${query.toString()}`)
  if (!res.ok) throw new Error(`Failed to check user: ${res.status}`)
  return res.json()
}

/**
 * Payload for creating a new user.
 *
 * Uses snake_case field names to match the backend's expected request body.
 * The role field uses title-case ("Admin" | "User") to match the backend enum.
 */
type CreateUserPayload = {
  username: string
  email: string
  first_name: string
  last_name: string
  phone_number: string
  password: string
  role: "Admin" | "User"
}

/**
 * Create a new user account.
 *
 * Sends a POST request to the backend with the user's profile information
 * and credentials. On success, the backend returns the created user object.
 *
 * @param payload - User creation data in snake_case format.
 * @returns The newly created user.
 * @throws Error with the backend's detail message if creation fails.
 */
export async function createUser(payload: CreateUserPayload): Promise<User> {
  const res = await authFetch(`${BASE}/users`, {
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

/**
 * Delete a user account by ID.
 *
 * This is a permanent, irreversible operation. The UI requires the admin
 * to type the username as confirmation before calling this function.
 *
 * @param userId - The ID of the user to delete.
 * @throws Error if the HTTP response is not OK (e.g. user not found).
 */
export async function deleteUser(userId: string): Promise<void> {
  const res = await authFetch(`${BASE}/users/${userId}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Failed to delete user: ${res.status}`)
}

/**
 * Activate a user account (set status to "active").
 *
 * Re-enables a previously deactivated account, allowing the user to log in again.
 *
 * @param userId - The ID of the user to activate.
 * @throws Error if the HTTP response is not OK.
 */
export async function activateUser(userId: string): Promise<void> {
  const res = await authFetch(`${BASE}/users/${userId}/activate`, { method: "PUT" })
  if (!res.ok) throw new Error(`Failed to activate user: ${res.status}`)
}

/**
 * Deactivate a user account (set status to "inactive").
 *
 * Disables the user account without deleting it. The user will not be able
 * to log in until an admin activates the account again.
 *
 * @param userId - The ID of the user to deactivate.
 * @throws Error if the HTTP response is not OK.
 */
export async function deactivateUser(userId: string): Promise<void> {
  const res = await authFetch(`${BASE}/users/${userId}/deactivate`, { method: "PUT" })
  if (!res.ok) throw new Error(`Failed to deactivate user: ${res.status}`)
}

/**
 * Modify an existing user's profile fields.
 *
 * Only the fields provided in the payload will be updated; omitted fields
 * remain unchanged. Username and role cannot be changed through this endpoint.
 *
 * @param userId - The ID of the user to modify.
 * @param payload - Partial profile data to update (snake_case keys).
 * @returns The updated user object.
 * @throws Error if the HTTP response is not OK.
 */
export async function modifyUser(
  userId: string,
  payload: { first_name?: string; last_name?: string; email?: string; phone_number?: string; password?: string },
): Promise<User> {
  const res = await authFetch(`${BASE}/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to modify user: ${res.status}`)
  return res.json()
}
