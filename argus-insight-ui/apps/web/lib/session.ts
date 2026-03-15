import { cookies } from "next/headers"

export interface SessionUser {
  name: string
  username: string
  email: string
  phone: string
  avatarUrl: string
}

export interface Session {
  user: SessionUser
}

/**
 * 현재 로그인된 사용자의 세션을 반환합니다.
 *
 * TODO: 로그인 구현 시 아래 순서로 작업하세요.
 *   1. 로그인 API 핸들러(예: app/api/auth/login/route.ts)에서 인증 성공 후
 *      cookies().set(SESSION_COOKIE_NAME, <서명된 JWT 또는 세션 토큰>) 으로 쿠키를 설정하세요.
 *   2. 이 함수에서 해당 쿠키 값을 읽어 JWT 검증 또는 세션 스토어 조회를 수행하세요.
 *   3. 유효하지 않은 세션이면 null을 반환하고, 호출 측에서 로그인 페이지로 리다이렉트하세요.
 */
export async function getSession(): Promise<Session> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME)

  if (sessionCookie?.value) {
    // TODO: 실제 구현 시 이 부분에서 JWT 검증 또는 세션 스토어 조회를 수행하세요.
    // 예: return verifyJwt(sessionCookie.value)
    //      return sessionStore.get(sessionCookie.value)
  }

  // 세션 쿠키가 없으면 개발용 mock 데이터를 반환합니다.
  // TODO: 실제 운영 환경에서는 이 fallback을 제거하고 로그인 페이지로 리다이렉트하세요.
  return MOCK_SESSION
}

// ──────────────────────────────────────────────
// 상수 및 개발용 Mock 데이터
// ──────────────────────────────────────────────

const SESSION_COOKIE_NAME = "argus_session"

const MOCK_SESSION: Session = {
  user: {
    name: "홍길동",
    username: "gildong.hong",
    email: "gildong@argus.io",
    phone: "010-1234-5678",
    avatarUrl: "/avatars/admin.png",
  },
}
