"use client"

import { useState } from "react"
import { ChevronUp, LogOut, Mail, Phone, Settings, Shield, User, User2 } from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@workspace/ui/components/avatar"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@workspace/ui/components/sidebar"
import { Separator } from "@workspace/ui/components/separator"
import type { SessionUser } from "@/lib/session"

interface AppSidebarUserProps {
  user: SessionUser
}

function getDisplayName(user: SessionUser): string {
  return `${user.lastName}${user.firstName}`.trim() || user.username
}

function getInitials(user: SessionUser): string {
  const last = user.lastName.charAt(0)
  const first = user.firstName.charAt(0)
  return (last + first).trim().toUpperCase() || user.username.charAt(0).toUpperCase()
}

export function AppSidebarUser({ user }: AppSidebarUserProps) {
  const [profileOpen, setProfileOpen] = useState(false)
  const displayName = getDisplayName(user)
  const initials = getInitials(user)

  return (
    <>
      <SidebarMenu>
        <SidebarMenuItem>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton
                size="lg"
                className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
              >
                <Avatar className="h-8 w-8 rounded-lg">
                  <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{displayName}</span>
                  <span className="truncate text-xs text-muted-foreground">{user.email}</span>
                </div>
                <ChevronUp className="ml-auto size-4" />
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
              side="bottom"
              align="end"
              sideOffset={4}
            >
              <DropdownMenuItem onSelect={() => setProfileOpen(true)}>
                <User2 className="mr-2 size-4" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Settings className="mr-2 size-4" />
                Account Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <LogOut className="mr-2 size-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>

      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Profile</DialogTitle>
          </DialogHeader>

          <div className="flex flex-col items-center gap-4 py-2">
            <Avatar className="h-16 w-16 rounded-full">
              <AvatarFallback className="rounded-full text-xl">{initials}</AvatarFallback>
            </Avatar>
            <div className="text-center">
              <p className="text-lg font-semibold">{displayName}</p>
              <p className="text-sm text-muted-foreground">@{user.username}</p>
            </div>
          </div>

          <Separator />

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm pt-2">
            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <User className="size-3.5" />
              Name
            </dt>
            <dd className="font-medium">{displayName}</dd>

            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <User2 className="size-3.5" />
              Username
            </dt>
            <dd className="font-medium">@{user.username}</dd>

            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <Mail className="size-3.5" />
              Email
            </dt>
            <dd className="font-medium">{user.email}</dd>

            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <Phone className="size-3.5" />
              Phone
            </dt>
            <dd className="font-medium">{user.phone}</dd>

            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <Shield className="size-3.5" />
              Role
            </dt>
            <dd className="font-medium">{user.role}</dd>
          </dl>
        </DialogContent>
      </Dialog>
    </>
  )
}
