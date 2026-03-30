"use client"

import { useEffect, useState } from "react"
import { ChevronsUpDown, Check, Container } from "lucide-react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"

import { cn } from "@workspace/ui/lib/utils"
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

interface MyWorkspace {
  id: number
  name: string
  display_name: string
  status: string
}

export function WorkspaceSwitcher() {
  const [open, setOpen] = useState(false)
  const [workspaces, setWorkspaces] = useState<MyWorkspace[]>([])
  const [selected, setSelected] = useState<MyWorkspace | null>(null)
  const { isMobile } = useSidebar()
  const router = useRouter()
  const searchParams = useSearchParams()
  const pathname = usePathname()

  // Fetch workspaces
  useEffect(() => {
    authFetch("/api/v1/workspace/workspaces/my")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setWorkspaces(data))
      .catch(() => setWorkspaces([]))
  }, [])

  // Sync selected state from URL ?ws= param
  useEffect(() => {
    const wsId = searchParams.get("ws")
    if (wsId && workspaces.length > 0) {
      const ws = workspaces.find((w) => w.id === Number(wsId))
      if (ws) setSelected(ws)
    }
  }, [searchParams, workspaces])

  const handleSelect = (ws: MyWorkspace) => {
    setSelected(ws)
    setOpen(false)
    router.push(`/dashboard/workspace?ws=${ws.id}`)
  }

  return (
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
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  )
}
