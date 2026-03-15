"use client"

import { useState } from "react"
import { ChevronUp, LogOut, Mail, Phone, Settings, User, User2 } from "lucide-react"

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

export function AppSidebarUser({ user }: AppSidebarUserProps) {
  const [profileOpen, setProfileOpen] = useState(false)

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
                  <AvatarImage src={user.avatarUrl} alt={user.name} />
                  <AvatarFallback className="rounded-lg">AD</AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{user.name}</span>
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
                프로필
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Settings className="mr-2 size-4" />
                계정 설정
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <LogOut className="mr-2 size-4" />
                로그아웃
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>

      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>프로필</DialogTitle>
          </DialogHeader>

          <div className="flex flex-col items-center gap-4 py-2">
            <Avatar className="h-16 w-16 rounded-full">
              <AvatarImage src={user.avatarUrl} alt={user.name} />
              <AvatarFallback className="rounded-full text-xl">AD</AvatarFallback>
            </Avatar>
            <div className="text-center">
              <p className="text-lg font-semibold">{user.name}</p>
              <p className="text-sm text-muted-foreground">@{user.username}</p>
            </div>
          </div>

          <Separator />

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm pt-2">
            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <User className="size-3.5" />
              이름
            </dt>
            <dd className="font-medium">{user.name}</dd>

            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <User2 className="size-3.5" />
              사용자명
            </dt>
            <dd className="font-medium">@{user.username}</dd>

            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <Mail className="size-3.5" />
              이메일
            </dt>
            <dd className="font-medium">{user.email}</dd>

            <dt className="flex items-center gap-1.5 text-muted-foreground">
              <Phone className="size-3.5" />
              전화번호
            </dt>
            <dd className="font-medium">{user.phone}</dd>
          </dl>
        </DialogContent>
      </Dialog>
    </>
  )
}
