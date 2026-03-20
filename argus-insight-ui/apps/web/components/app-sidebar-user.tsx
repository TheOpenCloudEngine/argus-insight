"use client"

import { useEffect, useState } from "react"
import {
  ChevronUp,
  Loader2,
  LogOut,
  Mail,
  Phone,
  Settings,
  Shield,
  ShieldCheck,
  User,
  User2,
} from "lucide-react"

import { Avatar, AvatarFallback } from "@workspace/ui/components/avatar"
import { Button } from "@workspace/ui/components/button"
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
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@workspace/ui/components/sidebar"
import { Separator } from "@workspace/ui/components/separator"
import type { SessionUser } from "@/lib/session"

const FALLBACK_USER: SessionUser = {
  id: 0,
  firstName: "",
  lastName: "",
  username: "",
  email: "",
  phone: "",
  role: "user",
}

function getDisplayName(user: SessionUser): string {
  return `${user.lastName}${user.firstName}`.trim() || user.username
}

function isAdmin(user: SessionUser): boolean {
  return user.role.toLowerCase() === "admin"
}

export function AppSidebarUser() {
  const [user, setUser] = useState<SessionUser>(FALLBACK_USER)
  const [profileOpen, setProfileOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch session data client-side to avoid making the dashboard layout
  // dynamic. In Next.js dev mode, server-side fetch() ignores the Data Cache,
  // which turns the layout dynamic and causes periodic full-screen refreshes.
  useEffect(() => {
    fetch("/api/v1/auth/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setUser({
            id: data.id,
            firstName: data.first_name,
            lastName: data.last_name,
            username: data.username,
            email: data.email,
            phone: data.phone_number || "",
            role: data.role,
          })
        }
      })
      .catch(() => {
        /* keep fallback */
      })
  }, [])

  // Form state for account settings
  const [formData, setFormData] = useState({
    firstName: user.firstName,
    lastName: user.lastName,
    email: user.email,
    phone: user.phone,
  })

  const displayName = getDisplayName(user)
  const admin = isAdmin(user)
  const RoleIcon = admin ? ShieldCheck : User

  function handleSettingsOpen() {
    setFormData({
      firstName: user.firstName,
      lastName: user.lastName,
      email: user.email,
      phone: user.phone,
    })
    setError(null)
    setSettingsOpen(true)
  }

  async function handleUpdate() {
    setSaving(true)
    setError(null)
    try {
      const res = await fetch("/api/v1/auth/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: formData.firstName,
          last_name: formData.lastName,
          email: formData.email,
          phone_number: formData.phone,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || "Failed to update profile")
      }
      // Update local user state instead of triggering a full page refresh
      setUser((prev) => ({
        ...prev,
        firstName: formData.firstName,
        lastName: formData.lastName,
        email: formData.email,
        phone: formData.phone,
      }))
      setSettingsOpen(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update profile")
    } finally {
      setSaving(false)
    }
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
              <DropdownMenuItem onSelect={handleSettingsOpen}>
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

      {/* Account Settings Dialog (editable) */}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Account Settings</DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            {/* Username (read-only, primary key) */}
            <div className="grid gap-2">
              <Label htmlFor="settings-username">Username</Label>
              <Input
                id="settings-username"
                value={user.username}
                disabled
                className="bg-muted"
              />
              <p className="text-xs text-muted-foreground">Username cannot be changed.</p>
            </div>

            {/* Role (read-only) */}
            <div className="grid gap-2">
              <Label htmlFor="settings-role">Role</Label>
              <Input
                id="settings-role"
                value={user.role}
                disabled
                className="bg-muted"
              />
            </div>

            <Separator />

            {/* Last Name */}
            <div className="grid gap-2">
              <Label htmlFor="settings-lastName">Last Name</Label>
              <Input
                id="settings-lastName"
                value={formData.lastName}
                onChange={(e) => setFormData((prev) => ({ ...prev, lastName: e.target.value }))}
              />
            </div>

            {/* First Name */}
            <div className="grid gap-2">
              <Label htmlFor="settings-firstName">First Name</Label>
              <Input
                id="settings-firstName"
                value={formData.firstName}
                onChange={(e) => setFormData((prev) => ({ ...prev, firstName: e.target.value }))}
              />
            </div>

            {/* Email */}
            <div className="grid gap-2">
              <Label htmlFor="settings-email">Email</Label>
              <Input
                id="settings-email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
              />
            </div>

            {/* Phone */}
            <div className="grid gap-2">
              <Label htmlFor="settings-phone">Phone</Label>
              <Input
                id="settings-phone"
                value={formData.phone}
                onChange={(e) => setFormData((prev) => ({ ...prev, phone: e.target.value }))}
              />
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setSettingsOpen(false)} disabled={saving}>
                Cancel
              </Button>
              <Button onClick={handleUpdate} disabled={saving}>
                {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
                Update
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
