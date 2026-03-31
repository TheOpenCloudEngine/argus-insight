"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronRight } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@workspace/ui/components/collapsible"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@workspace/ui/components/sidebar"
import { getIcon } from "@/lib/icon-map"
import { useAuth } from "@/features/auth"
import type { MenuItem, MenuGroup } from "@/types/menu"

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
              if (item.children?.length) {
                return (
                  <CollapsibleMenuItem
                    key={item.id}
                    item={item}
                    pathname={pathname}
                  />
                )
              }

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

function CollapsibleMenuItem({
  item,
  pathname,
}: {
  item: MenuItem
  pathname: string
}) {
  const Icon = getIcon(item.icon)
  const isActive =
    pathname === item.url ||
    pathname.startsWith(item.url + "/") ||
    item.children?.some(
      (child) =>
        pathname === child.url || pathname.startsWith(child.url + "/"),
    )

  return (
    <Collapsible asChild defaultOpen={isActive} className="group/collapsible">
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton
            tooltip={item.title}
            isActive={pathname === item.url}
            className="text-sm"
          >
            <Icon />
            <span>{item.title}</span>
            <ChevronRight className="ml-auto h-4 w-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarMenuSub>
            {item.children?.map((child) => {
              const isChildActive =
                pathname === child.url || pathname.startsWith(child.url + "/")
              return (
                <SidebarMenuSubItem key={child.id}>
                  <SidebarMenuSubButton asChild isActive={isChildActive}>
                    <Link href={child.url} prefetch={false}>
                      <span>{child.title}</span>
                    </Link>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              )
            })}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}
