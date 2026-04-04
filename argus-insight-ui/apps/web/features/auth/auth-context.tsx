"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import {
  login as apiLogin,
  logout as apiLogout,
  refreshToken as apiRefreshToken,
  fetchMe,
  type TokenResponse,
  type UserInfo,
} from "./api"

type AuthState = {
  user: UserInfo | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

const TOKEN_KEY = "argus_tokens"

type StoredTokens = {
  access_token: string
  refresh_token: string
  expires_at: number
}

function saveTokens(tokens: TokenResponse) {
  const data: StoredTokens = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    expires_at: Date.now() + tokens.expires_in * 1000,
  }
  sessionStorage.setItem(TOKEN_KEY, JSON.stringify(data))
}

function loadTokens(): StoredTokens | null {
  try {
    const raw = sessionStorage.getItem(TOKEN_KEY)
    if (!raw) return null
    return JSON.parse(raw) as StoredTokens
  } catch {
    return null
  }
}

function clearTokens() {
  sessionStorage.removeItem(TOKEN_KEY)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scheduleRefresh = useCallback((tokens: StoredTokens) => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current)
    }
    // Refresh 60 seconds before expiry
    const msUntilRefresh = tokens.expires_at - Date.now() - 60_000
    if (msUntilRefresh <= 0) return

    refreshTimerRef.current = setTimeout(async () => {
      try {
        const stored = loadTokens()
        if (!stored) return
        const newTokens = await apiRefreshToken(stored.refresh_token)
        saveTokens(newTokens)
        setAccessToken(newTokens.access_token)
        scheduleRefresh({
          access_token: newTokens.access_token,
          refresh_token: newTokens.refresh_token,
          expires_at: Date.now() + newTokens.expires_in * 1000,
        })
      } catch {
        // Refresh failed - force logout
        clearTokens()
        setUser(null)
        setAccessToken(null)
      }
    }, msUntilRefresh)
  }, [])

  // Initialize from stored tokens on mount
  useEffect(() => {
    async function init() {
      const stored = loadTokens()
      if (!stored) {
        setIsLoading(false)
        return
      }

      // Check if token is still valid (with some buffer)
      if (stored.expires_at < Date.now() + 10_000) {
        // Try to refresh
        try {
          const newTokens = await apiRefreshToken(stored.refresh_token)
          saveTokens(newTokens)
          const userInfo = await fetchMe(newTokens.access_token)
          setAccessToken(newTokens.access_token)
          setUser(userInfo)
          scheduleRefresh({
            access_token: newTokens.access_token,
            refresh_token: newTokens.refresh_token,
            expires_at: Date.now() + newTokens.expires_in * 1000,
          })
        } catch {
          clearTokens()
        }
      } else {
        // Token still valid
        try {
          const userInfo = await fetchMe(stored.access_token)
          setAccessToken(stored.access_token)
          setUser(userInfo)
          scheduleRefresh(stored)
        } catch {
          clearTokens()
        }
      }
      setIsLoading(false)
    }

    init()

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current)
      }
    }
  }, [scheduleRefresh])

  const login = useCallback(
    async (username: string, password: string) => {
      const tokens = await apiLogin(username, password)
      saveTokens(tokens)
      const userInfo = await fetchMe(tokens.access_token)
      setAccessToken(tokens.access_token)
      setUser(userInfo)
      scheduleRefresh({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: Date.now() + tokens.expires_in * 1000,
      })
    },
    [scheduleRefresh]
  )

  const logout = useCallback(async () => {
    const stored = loadTokens()
    if (stored) {
      await apiLogout(stored.refresh_token).catch(() => {})
    }
    clearTokens()
    sessionStorage.removeItem("argus_last_workspace_id")
    setUser(null)
    setAccessToken(null)
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current)
    }
  }, [])

  const value = useMemo(
    () => ({
      user,
      accessToken,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
    }),
    [user, accessToken, isLoading, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return ctx
}
