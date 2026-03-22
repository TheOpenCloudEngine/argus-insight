"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"
import { Brain, Search } from "lucide-react"

import { Input } from "@workspace/ui/components/input"
import { Separator } from "@workspace/ui/components/separator"
import { SidebarTrigger } from "@workspace/ui/components/sidebar"
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from "@workspace/ui/components/tooltip"

interface DashboardHeaderProps {
  title: string
}

export function DashboardHeader({ title }: DashboardHeaderProps) {
  const router = useRouter()
  const [query, setQuery] = useState("")

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && query.trim()) {
      router.push(`/dashboard/search?q=${encodeURIComponent(query.trim())}`)
    }
  }

  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <div className="flex flex-1 items-center gap-2">
        <h1 className="text-xl font-semibold leading-none">{title}</h1>
      </div>
      <div className="flex items-center gap-2 ml-auto">
        <div className="relative hidden md:block">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search datasets by name, description, or meaning..."
            className="pl-8 w-96 h-9 text-sm"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="hidden md:flex items-center">
              <Brain className="h-4 w-4 text-purple-500" />
            </div>
          </TooltipTrigger>
          <TooltipContent>Hybrid search (keyword + semantic)</TooltipContent>
        </Tooltip>
      </div>
    </header>
  )
}
