"use client"

import { useCallback, useState, useMemo } from "react"
import { Loader2, RefreshCw, Search } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Badge } from "@workspace/ui/components/badge"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@workspace/ui/components/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@workspace/ui/components/sheet"
import { Separator } from "@workspace/ui/components/separator"
import type { PluginResponse } from "@/features/software-deployment/types"
import { fetchPlugins, rescanPlugins } from "@/features/software-deployment/api"
import { PluginIcon } from "@/features/software-deployment/components/plugin-icon"

interface CatalogCardTabProps {
  plugins: PluginResponse[]
  onPluginsChanged: () => void
}

function statusColor(status: string) {
  switch (status) {
    case "stable":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
    case "beta":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
    case "deprecated":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
    default:
      return ""
  }
}

/* ------------------------------------------------------------------ */
/*  Plugin Detail Sheet                                                */
/* ------------------------------------------------------------------ */

function PluginDetailSheet({
  plugin,
  open,
  onOpenChange,
}: {
  plugin: PluginResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!plugin) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[420px] overflow-y-auto sm:max-w-[420px]">
        <SheetHeader className="pb-4">
          <div className="flex items-center gap-3">
            <PluginIcon icon={plugin.icon} size={40} className="shrink-0 rounded" />
            <div>
              <SheetTitle className="text-base">
                {plugin.display_name}
                {plugin.versions[0]?.software_version && (
                  <span className="ml-2 text-sm font-normal text-muted-foreground font-mono">
                    v{plugin.versions[0].software_version}
                  </span>
                )}
              </SheetTitle>
              <SheetDescription className="text-xs">{plugin.category} · {plugin.source}</SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="space-y-5">
          {/* Description */}
          <p className="text-sm">{plugin.description}</p>

          <Separator />

          {/* Details */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Details</h4>
            <div className="grid grid-cols-[100px_1fr] gap-y-1.5 text-sm">
              <span className="text-muted-foreground">Plugin ID</span>
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">{plugin.name}</code>
              <span className="text-muted-foreground">Category</span>
              <span>{plugin.category}</span>
              <span className="text-muted-foreground">Source</span>
              <Badge variant="outline" className="w-fit text-xs">{plugin.source}</Badge>
              {plugin.enabled !== null && (
                <>
                  <span className="text-muted-foreground">In Pipeline</span>
                  <span>{plugin.enabled ? "Yes" : "No"}</span>
                </>
              )}
            </div>
          </div>

          {/* Tags */}
          {plugin.tags.length > 0 && (
            <>
              <Separator />
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Tags</h4>
                <div className="flex flex-wrap gap-1.5">
                  {plugin.tags.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Dependencies */}
          <Separator />
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Dependencies</h4>
            <div className="grid grid-cols-[100px_1fr] gap-y-1.5 text-sm">
              <span className="text-muted-foreground">Depends on</span>
              <span>{plugin.depends_on.length > 0 ? plugin.depends_on.join(", ") : "None"}</span>
              <span className="text-muted-foreground">Provides</span>
              <div>
                {plugin.provides.length > 0 ? (
                  plugin.provides.map((p) => (
                    <code key={p} className="mr-1 mb-1 inline-block rounded bg-muted px-1.5 py-0.5 text-xs font-mono">{p}</code>
                  ))
                ) : (
                  <span>None</span>
                )}
              </div>
              <span className="text-muted-foreground">Requires</span>
              <div>
                {plugin.requires.length > 0 ? (
                  plugin.requires.map((r) => (
                    <code key={r} className="mr-1 mb-1 inline-block rounded bg-muted px-1.5 py-0.5 text-xs font-mono">{r}</code>
                  ))
                ) : (
                  <span>None</span>
                )}
              </div>
            </div>
          </div>

          {/* Versions */}
          {plugin.versions.length > 0 && (
            <>
              <Separator />
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Versions</h4>
                {plugin.versions.map((v) => (
                  <div key={v.version} className="rounded-lg border p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{v.display_name}</span>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(v.status)}`}>
                        {v.status}
                      </span>
                    </div>
                    <div className="grid grid-cols-[80px_1fr] gap-y-1 text-xs">
                      {v.software_version && (
                        <>
                          <span className="text-muted-foreground">Software</span>
                          <span className="font-mono">v{v.software_version}</span>
                        </>
                      )}
                      {v.os_key && (
                        <>
                          <span className="text-muted-foreground">OS</span>
                          <span>{v.os_key}</span>
                        </>
                      )}
                      {v.release_date && (
                        <>
                          <span className="text-muted-foreground">Released</span>
                          <span>{new Date(v.release_date).toLocaleDateString()}</span>
                        </>
                      )}
                    </div>
                    {v.changelog && (
                      <div className="text-xs text-muted-foreground whitespace-pre-line pt-1">
                        {v.changelog}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function CatalogCardTab({
  plugins: initialPlugins,
  onPluginsChanged,
}: CatalogCardTabProps) {
  const [localPlugins, setLocalPlugins] = useState<PluginResponse[]>(initialPlugins)
  const [rescanning, setRescanning] = useState(false)
  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("all")
  const [sourceFilter, setSourceFilter] = useState("all")
  const [selectedPlugin, setSelectedPlugin] = useState<PluginResponse | null>(null)

  useMemo(() => { setLocalPlugins(initialPlugins) }, [initialPlugins])

  const handleRescan = useCallback(async () => {
    setRescanning(true)
    try {
      await rescanPlugins()
      const data = await fetchPlugins()
      setLocalPlugins(data)
      onPluginsChanged()
    } catch { /* ignore */ }
    setRescanning(false)
  }, [onPluginsChanged])

  const categories = useMemo(() => {
    const unique = new Set(localPlugins.map((p) => p.category))
    return Array.from(unique).sort()
  }, [localPlugins])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return localPlugins.filter((p) => {
      if (categoryFilter !== "all" && p.category !== categoryFilter) return false
      if (sourceFilter !== "all" && p.source !== sourceFilter) return false
      if (q && !p.name.toLowerCase().includes(q) && !p.display_name.toLowerCase().includes(q) && !p.description.toLowerCase().includes(q) && !p.tags.some((t) => t.toLowerCase().includes(q))) return false
      return true
    })
  }, [localPlugins, search, categoryFilter, sourceFilter])

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1">
          <Search className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
          <Input placeholder="Search plugins..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]"><SelectValue placeholder="Category" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {categories.map((cat) => (<SelectItem key={cat} value={cat}>{cat}</SelectItem>))}
          </SelectContent>
        </Select>
        <Select value={sourceFilter} onValueChange={setSourceFilter}>
          <SelectTrigger className="w-[150px]"><SelectValue placeholder="Source" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Sources</SelectItem>
            <SelectItem value="builtin">Builtin</SelectItem>
            <SelectItem value="external">External</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={handleRescan} disabled={rescanning}>
          {rescanning ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-1.5 h-4 w-4" />}
          Rescan Plugins
        </Button>
      </div>

      {/* Card Grid */}
      {filtered.length === 0 ? (
        <div className="text-muted-foreground py-12 text-center text-sm">No plugins found.</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((plugin) => {
            const latestVersion = plugin.versions[0]
            const isSelected = selectedPlugin?.name === plugin.name

            return (
              <Card
                key={plugin.name}
                className={`cursor-pointer transition-colors hover:bg-muted/50 ${isSelected ? "ring-primary ring-2" : ""}`}
                onClick={() => setSelectedPlugin(isSelected ? null : plugin)}
              >
                <CardHeader className="flex flex-row items-start gap-3 pb-2">
                  <PluginIcon icon={plugin.icon} size={36} className="shrink-0 rounded" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate text-sm font-semibold">{plugin.display_name}</h3>
                      {latestVersion?.software_version && (
                        <span className="shrink-0 text-xs text-muted-foreground font-mono">v{latestVersion.software_version}</span>
                      )}
                    </div>
                    <p className="text-muted-foreground text-xs">{plugin.category}</p>
                  </div>
                  {plugin.enabled !== null && plugin.enabled && (
                    <Badge variant="secondary" className="shrink-0 text-[10px]">In Pipeline</Badge>
                  )}
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-foreground line-clamp-2 text-sm">{plugin.description}</p>
                </CardContent>
                <CardFooter className="flex flex-wrap gap-1 pt-0">
                  {plugin.tags.slice(0, 3).map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
                  ))}
                  {plugin.tags.length > 3 && (
                    <span className="text-muted-foreground text-xs">+{plugin.tags.length - 3}</span>
                  )}
                  <div className="flex-1" />
                  {latestVersion?.software_version && (
                    <Badge variant="secondary" className="text-xs font-mono">v{latestVersion.software_version}</Badge>
                  )}
                </CardFooter>
              </Card>
            )
          })}
        </div>
      )}

      {/* Detail Sheet (right slide-out) */}
      <PluginDetailSheet
        plugin={selectedPlugin}
        open={!!selectedPlugin}
        onOpenChange={(open) => { if (!open) setSelectedPlugin(null) }}
      />
    </div>
  )
}
