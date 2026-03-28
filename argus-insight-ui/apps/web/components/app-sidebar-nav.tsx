"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@workspace/ui/components/sidebar"
import { getIcon } from "@/lib/icon-map"
import { useAuth } from "@/features/auth"
import type { MenuGroup } from "@/types/menu"

interface AppSidebarNavProps {
  groups: MenuGroup[]
}

export function AppSidebarNav({ groups }: AppSidebarNavProps) {
  const pathname = usePathname()
  const { user } = useAuth()

  return (
    <>
      {groups.map((group) => {
        // Administration group is only visible to admins
        if (group.id === "admin" && !user?.is_admin) return null

        return (
        <SidebarGroup key={group.id}>
          <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
          <SidebarMenu>
            {group.items
              .filter((item) => !item.adminOnly || user?.is_admin)
              .map((item) => {
              const Icon = getIcon(item.icon)
              return (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    asChild
                    isActive={pathname === item.url || (item.url !== "/dashboard" && pathname.startsWith(item.url + "/"))}
                    tooltip={item.title}
                    className="text-sm"
                  >
                    <Link href={item.url} prefetch={false}>
                      <Icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )
            })}
          </SidebarMenu>
        </SidebarGroup>
        )
      })}
    </>
  )
}
