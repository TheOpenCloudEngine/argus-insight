/**
 * Authentication API client.
 *
 * Communicates with the backend /api/v1/auth/* endpoints
 * which proxy to Keycloak for token management.
 */

const BASE = "/api/v1/auth"

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  refresh_expires_in: number
}

export type UserInfo = {
  sub: string
  username: string
  email: string
  first_name: string
  last_name: string
  roles: string[]
  realm_roles: string[]
  role: string
  is_admin: boolean
  is_superuser: boolean
}

export async function login(
  username: string,
  password: string
): Promise<TokenResponse> {
  const res = await fetch(`${BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || "Login failed")
  }
  return res.json()
}

export async function refreshToken(
  refresh_token: string
): Promise<TokenResponse> {
  const res = await fetch(`${BASE}/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  })
  if (!res.ok) {
    throw new Error("Token refresh failed")
  }
  return res.json()
}

export async function fetchMe(accessToken: string): Promise<UserInfo> {
  const res = await fetch(`${BASE}/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!res.ok) {
    throw new Error("Failed to fetch user info")
  }
  return res.json()
}

export async function logout(refresh_token: string): Promise<void> {
  await fetch(`${BASE}/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  })
}
