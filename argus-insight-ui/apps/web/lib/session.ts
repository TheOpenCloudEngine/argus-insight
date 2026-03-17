export interface SessionUser {
  firstName: string
  lastName: string
  username: string
  email: string
  phone: string
  role: string
}

export interface Session {
  user: SessionUser
}

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:4500"

/**
 * 현재 로그인된 사용자의 세션을 반환합니다.
 *
 * FIXME: 현재는 인증 없이 서버에서 argus_users.id=1 사용자를 강제로 반환합니다.
 *        실제 인증이 구현되면 Authorization 헤더에 토큰을 포함하여 요청해야 합니다.
 */
export async function getSession(): Promise<Session> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      cache: "no-store",
    })
    if (!res.ok) {
      console.error("Failed to fetch session:", res.status, res.statusText)
      return FALLBACK_SESSION
    }
    const data = await res.json()
    return {
      user: {
        firstName: data.first_name,
        lastName: data.last_name,
        username: data.username,
        email: data.email,
        phone: data.phone_number || "",
        role: data.role,
      },
    }
  } catch (error) {
    console.error("Failed to fetch session:", error)
    return FALLBACK_SESSION
  }
}

// ──────────────────────────────────────────────
// API 호출 실패 시 폴백 데이터
// ──────────────────────────────────────────────

const FALLBACK_SESSION: Session = {
  user: {
    firstName: "Unknown",
    lastName: "",
    username: "unknown",
    email: "",
    phone: "",
    role: "user",
  },
}
