"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import {
  ChevronUp,
  Eye,
  EyeOff,
  GitBranch,
  Key,
  LogOut,
  Mail,
  Package,
  Settings,
  Shield,
  ShieldAlert,
  ShieldCheck,
  User,
  User2,
} from "lucide-react"

import { Avatar, AvatarFallback } from "@workspace/ui/components/avatar"
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
import { useAuth } from "@/features/auth"
import { UsersActionDialog } from "@/features/users/components/users-action-dialog"
import type { User as UserType } from "@/features/users/data/schema"

export function AppSidebarUser() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const [profileOpen, setProfileOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [showSecretKey, setShowSecretKey] = useState(false)
  const [showGitlabPassword, setShowGitlabPassword] = useState(false)

  if (!user) return null

  const displayName =
    `${user.last_name ?? ""}${user.first_name ?? ""}`.trim() || user.username

  const RoleIcon = user.is_admin
    ? ShieldCheck
    : user.is_superuser
      ? ShieldAlert
      : User
  const roleName =
    user.role === "admin"
      ? "Admin"
      : user.role === "superuser"
        ? "Superuser"
        : "User"

  // Build a User object for UsersActionDialog (edit mode)
  const currentUserAsRow: UserType = {
    id: user.sub,
    firstName: user.first_name,
    lastName: user.last_name,
    username: user.username,
    email: user.email,
    phoneNumber: "",
    status: "active" as const,
    role: (user.is_admin ? "admin" : "user") as "admin" | "user",
    createdAt: new Date(),
    updatedAt: new Date(),
  }

  async function handleLogout() {
    await logout()
    router.replace("/login")
  }

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
                  <AvatarFallback className="rounded-lg">
                    <RoleIcon className="size-4" />
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{displayName}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {user.email}
                  </span>
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
              <DropdownMenuItem onSelect={() => setSettingsOpen(true)}>
                <Settings className="mr-2 size-4" />
                Account Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={handleLogout}>
                <LogOut className="mr-2 size-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>

      {/* Profile Dialog (read-only) */}
      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Profile</DialogTitle>
          </DialogHeader>

          <div className="flex flex-col items-center gap-4 py-2">
            <Avatar className="h-16 w-16 rounded-full">
              <AvatarFallback className="rounded-full">
                <RoleIcon className="size-7" />
              </AvatarFallback>
            </Avatar>
            <div className="text-center">
              <p className="text-lg font-semibold">{displayName}</p>
              <p className="text-sm text-muted-foreground">@{user.username}</p>
            </div>
          </div>

          <Separator />

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm py-2">
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
              <Shield className="size-3.5" />
              Role
            </dt>
            <dd className="font-medium">{roleName}</dd>
          </dl>

          {user.s3_access_key && (
            <>
              <Separator />
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm py-2">
                  <dt className="flex items-center gap-1.5 text-muted-foreground">
                    <Package className="size-3.5" />
                    Bucket
                  </dt>
                  <dd className="font-mono text-xs">{user.s3_bucket}</dd>

                  <dt className="flex items-center gap-1.5 text-muted-foreground">
                    <Key className="size-3.5" />
                    Access Key
                  </dt>
                  <dd className="font-mono text-xs">{user.s3_access_key}</dd>

                  <dt className="flex items-center gap-1.5 text-muted-foreground">
                    <Key className="size-3.5" />
                    Secret Key
                  </dt>
                  <dd className="flex items-center gap-1.5">
                    <span className="font-mono text-xs">
                      {showSecretKey ? user.s3_secret_key : "••••••••••••••••"}
                    </span>
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground"
                      onClick={() => setShowSecretKey(!showSecretKey)}
                    >
                      {showSecretKey ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                    </button>
                  </dd>
                </dl>
            </>
          )}

          {user.gitlab_username && (
            <>
              <Separator />
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm py-2">
                  <dt className="flex items-center gap-1.5 text-muted-foreground">
                    <GitBranch className="size-3.5" />
                    GitLab Username
                  </dt>
                  <dd className="font-mono text-xs">{user.gitlab_username}</dd>

                  <dt className="flex items-center gap-1.5 text-muted-foreground">
                    <Key className="size-3.5" />
                    GitLab Password
                  </dt>
                  <dd className="flex items-center gap-1.5">
                    <span className="font-mono text-xs">
                      {showGitlabPassword ? user.gitlab_password : "••••••••••••••••"}
                    </span>
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground"
                      onClick={() => setShowGitlabPassword(!showGitlabPassword)}
                    >
                      {showGitlabPassword ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                    </button>
                  </dd>
                </dl>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Account Settings — reuse UsersActionDialog in edit mode, without Role */}
      <UsersActionDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        currentRow={currentUserAsRow}
        hideRole
        onSaved={() => window.location.reload()}
      />
    </>
  )
}
