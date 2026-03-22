// Added for SSO AUTH - sidebar footer component displaying current user info and logout button.
"use client"

import { LogOut, User } from "lucide-react"
import { useRouter } from "next/navigation"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@workspace/ui/components/sidebar"
import { useAuth } from "@/features/auth"

export function SidebarUser() {
  const { user, logout } = useAuth()
  const router = useRouter()

  if (!user) return null

  async function handleLogout() {
    await logout()
    router.replace("/login")
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size="lg" className="cursor-default">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <User className="size-4" />
          </div>
          <div className="flex flex-col gap-0.5 leading-none group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-medium">{user.username}</span>
            <span className="text-xs text-muted-foreground">{user.email}</span>
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
      <SidebarMenuItem>
        <SidebarMenuButton size="sm" onClick={handleLogout}>
          <LogOut className="size-4" />
          <span className="group-data-[collapsible=icon]:hidden">Sign out</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
