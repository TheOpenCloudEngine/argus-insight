import Link from "next/link"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter, // Added for SSO AUTH
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@workspace/ui/components/sidebar"
import { AppSidebarNav } from "@/components/app-sidebar-nav"
import { SidebarUser } from "@/components/sidebar-user" // Added for SSO AUTH
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
                <div className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-md text-sm font-bold group-data-[collapsible=icon]:flex">
                  AC
                </div>
                <span className="truncate text-lg font-bold group-data-[collapsible=icon]:hidden">
                  Argus Catalog
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <AppSidebarNav groups={menu.groups} />
      </SidebarContent>

      {/* Added for SSO AUTH - displays current user info and logout button */}
      <SidebarFooter>
        <SidebarUser />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
