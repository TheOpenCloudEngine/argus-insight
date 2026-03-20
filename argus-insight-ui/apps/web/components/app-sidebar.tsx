// import { Shield } from "lucide-react"
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

export async function AppSidebar() {
  const menu = await getMenu()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/dashboard">
                {/* TODO: Replace with actual logo image
                <div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <Shield className="size-4" />
                </div>
                */}
                <div className="grid flex-1 text-left leading-tight">
                  <span className="truncate text-lg font-bold">Argus Insight</span>
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
        <AppSidebarUser />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
