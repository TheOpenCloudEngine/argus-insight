"use client"

import { useEffect, useState } from "react"
import { ChevronsUpDown, Check, Container, Loader2, Plus } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"

import { cn } from "@workspace/ui/lib/utils"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@workspace/ui/components/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@workspace/ui/components/command"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@workspace/ui/components/sidebar"
import { authFetch } from "@/features/auth/auth-fetch"
import { useAuth } from "@/features/auth"

interface MyWorkspace {
  id: number
  name: string
  display_name: string
  status: string
}

const NAME_REGEX = /^[a-z][a-z0-9_]*$/

function validateName(name: string): string | null {
  if (!name) return "Name is required."
  if (name.length >= 12) return "Name must be less than 12 characters."
  if (!/^[a-z]/.test(name)) return "Must start with a lowercase letter."
  if (!NAME_REGEX.test(name)) return "Only lowercase letters, numbers, and _ are allowed."
  return null
}

export function WorkspaceSwitcher() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [workspaces, setWorkspaces] = useState<MyWorkspace[]>([])
  const [selected, setSelected] = useState<MyWorkspace | null>(null)
  const { isMobile } = useSidebar()
  const router = useRouter()
  const searchParams = useSearchParams()

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false)
  const [wsName, setWsName] = useState("")
  const [wsDisplayName, setWsDisplayName] = useState("")
  const [wsDescription, setWsDescription] = useState("")
  const [nameError, setNameError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const fetchWorkspaces = () => {
    authFetch("/api/v1/workspace/workspaces/my")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setWorkspaces(data))
      .catch(() => setWorkspaces([]))
  }

  useEffect(() => { fetchWorkspaces() }, [])

  // Sync selected state from URL ?ws= param or sessionStorage
  useEffect(() => {
    if (workspaces.length === 0) return
    const wsId = searchParams.get("ws")
    if (wsId) {
      const ws = workspaces.find((w) => w.id === Number(wsId))
      if (ws) setSelected(ws)
    } else {
      // Fallback: sync from sessionStorage (e.g. set by ML Studio)
      const stored = sessionStorage.getItem("argus_last_workspace_id")
      if (stored) {
        const ws = workspaces.find((w) => w.id === Number(stored))
        if (ws && (!selected || selected.id !== ws.id)) setSelected(ws)
      }
    }
  }, [searchParams, workspaces])

  // Listen for workspace changes from other components (e.g. ML Studio page)
  useEffect(() => {
    const handler = (e: Event) => {
      const wsId = (e as CustomEvent).detail?.workspaceId
      if (wsId && workspaces.length > 0) {
        const ws = workspaces.find((w) => w.id === wsId)
        if (ws) setSelected(ws)
      }
    }
    window.addEventListener("argus:workspace-changed", handler)
    return () => window.removeEventListener("argus:workspace-changed", handler)
  }, [workspaces])

  const handleSelect = (ws: MyWorkspace) => {
    setSelected(ws)
    setOpen(false)
    sessionStorage.setItem("argus_last_workspace_id", String(ws.id))
    router.push(`/dashboard/workspace?ws=${ws.id}`)
  }

  const openCreateDialog = () => {
    setOpen(false)
    setWsName("")
    setWsDisplayName("")
    setWsDescription("")
    setNameError(null)
    setCreateError(null)
    setCreating(false)
    setCreateOpen(true)
  }

  const handleNameChange = (value: string) => {
    const cleaned = value.toLowerCase().replace(/[^a-z0-9_]/g, "")
    setWsName(cleaned)
    setNameError(null)
    setCreateError(null)
  }

  const handleCreate = async () => {
    // Validate
    const err = validateName(wsName)
    if (err) { setNameError(err); return }
    if (!wsDisplayName.trim()) { setNameError(null); setCreateError("Display name is required."); return }

    setCreating(true)
    setCreateError(null)

    try {
      // Check name availability
      const checkRes = await authFetch(`/api/v1/workspace/workspaces/check?name=${wsName}`)
      if (checkRes.ok) {
        const checkData = await checkRes.json()
        if (checkData.exists) {
          setNameError("This name is already taken.")
          setCreating(false)
          return
        }
      }

      // Load domain from settings
      let domain = "localhost"
      try {
        const cfgRes = await authFetch("/api/v1/settings/configuration")
        if (cfgRes.ok) {
          const cfgData = await cfgRes.json()
          const domainCat = cfgData.categories?.find((c: { category: string }) => c.category === "domain")
          if (domainCat?.items?.domain_name) domain = domainCat.items.domain_name
        }
      } catch { /* use default */ }

      // Get current user ID
      const adminUserId = user ? parseInt(user.sub) : 1

      // Create workspace
      const res = await authFetch("/api/v1/workspace/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: wsName,
          display_name: wsDisplayName.trim(),
          description: wsDescription.trim() || null,
          domain,
          admin_user_id: adminUserId,
          pipeline_ids: [],
        }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || `Failed: ${res.status}`)
      }

      const created = await res.json()
      setCreateOpen(false)
      fetchWorkspaces()
      // Navigate to the new workspace
      router.push(`/dashboard/workspace?ws=${created.id}`)
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Failed to create workspace")
    }
    setCreating(false)
  }

  return (
    <>
      <SidebarGroup>
        <SidebarGroupLabel>Workspace</SidebarGroupLabel>
        <SidebarMenu>
          <SidebarMenuItem>
            <Popover open={open} onOpenChange={setOpen}>
              <PopoverTrigger asChild>
                <SidebarMenuButton
                  tooltip={selected?.display_name ?? "Select workspace"}
                  className="text-sm justify-between"
                >
                  <Container className="h-4 w-4 shrink-0" />
                  <span className="truncate flex-1 group-data-[collapsible=icon]:hidden">
                    {selected?.display_name ?? "Select workspace"}
                  </span>
                  <ChevronsUpDown className="ml-auto h-4 w-4 shrink-0 opacity-50 group-data-[collapsible=icon]:hidden" />
                </SidebarMenuButton>
              </PopoverTrigger>
              <PopoverContent
                className="w-[--radix-popover-trigger-width] min-w-56 p-0"
                align="start"
                side={isMobile ? "bottom" : "right"}
                sideOffset={4}
              >
                <Command>
                  <CommandInput placeholder="Search workspace..." />
                  <CommandList>
                    <CommandEmpty>No workspace found.</CommandEmpty>
                    <CommandGroup>
                      {workspaces.map((ws) => (
                        <CommandItem
                          key={ws.id}
                          value={ws.name}
                          onSelect={() => handleSelect(ws)}
                        >
                          <span className="flex-1">{ws.display_name}</span>
                          <span className="text-xs text-muted-foreground">{ws.name}</span>
                          <Check
                            className={cn(
                              "ml-2 h-4 w-4",
                              selected?.id === ws.id ? "opacity-100" : "opacity-0"
                            )}
                          />
                        </CommandItem>
                      ))}
                    </CommandGroup>
                    <CommandGroup>
                      <CommandItem onSelect={openCreateDialog} className="text-muted-foreground">
                        <Plus className="mr-2 h-4 w-4" />
                        Create Workspace
                      </CommandItem>
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>

      {/* Create Workspace Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Create Workspace</DialogTitle>
            <DialogDescription>Create a new workspace. You will be the owner.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Name <span className="text-destructive">*</span></Label>
              <Input
                value={wsName}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="myworkspace"
                maxLength={11}
              />
              {nameError && <p className="text-xs text-destructive">{nameError}</p>}
              <p className="text-xs text-muted-foreground">Lowercase letters, numbers, _ only. Max 11 chars.</p>
            </div>
            <div className="space-y-1.5">
              <Label>Display Name <span className="text-destructive">*</span></Label>
              <Input
                value={wsDisplayName}
                onChange={(e) => setWsDisplayName(e.target.value)}
                placeholder="My Workspace"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input
                value={wsDescription}
                onChange={(e) => setWsDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
            {createError && (
              <div className="rounded-md bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-sm dark:bg-red-950 dark:text-red-200 dark:border-red-800">
                {createError}
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)} disabled={creating}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleCreate} disabled={creating || !wsName || !wsDisplayName.trim()}>
              {creating && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Create
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
