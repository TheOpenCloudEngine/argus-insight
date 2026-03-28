"use client"

import type { ReactNode } from "react"
import { AuthGuard } from "@/features/auth"

export function AuthGuardWrapper({ children }: { children: ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>
}
