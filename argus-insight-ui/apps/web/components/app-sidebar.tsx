import { Shield } from "lucide-react"
import Link from "next/link"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@workspace/ui/components/sidebar"
import { AppSidebarNav } from "@/components/app-sidebar-nav"
import { AppSidebarUser } from "@/components/app-sidebar-user"
import { getMenu } from "@/lib/menu"
import { getSession } from "@/lib/session"

export async function AppSidebar() {
  const [menu, session] = await Promise.all([getMenu(), getSession()])

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/dashboard">
                <div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <Shield className="size-4" />
                </div>
                <div className="grid flex-1 text-left leading-tight">
                  <span className="truncate text-base font-bold">Argus</span>
                  <span className="truncate text-xs text-muted-foreground">Data + AI Platform</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <AppSidebarNav groups={menu.groups} />
      </SidebarContent>

      <SidebarFooter>
        <AppSidebarUser user={session.user} />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
