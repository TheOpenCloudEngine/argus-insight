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
                <div className="grid flex-1 text-left leading-tight">
                  <span className="truncate text-lg font-bold">
                    <span className="group-data-[collapsible=icon]:hidden">Argus Insight</span>
                    <span className="hidden group-data-[collapsible=icon]:inline">AI</span>
                  </span>
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
