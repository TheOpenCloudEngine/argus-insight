"use client"

import { useCallback, useState, useMemo } from "react"
import { Loader2, RefreshCw, Search } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import type { PluginResponse } from "@/features/software-deployment/types"
import { fetchPlugins, rescanPlugins } from "@/features/software-deployment/api"
import { CatalogDetail } from "@/features/software-deployment/components/catalog-detail"

interface CatalogTabProps {
  plugins: PluginResponse[]
  onPluginsChanged: () => void
}

export function CatalogTab({ plugins: initialPlugins, onPluginsChanged }: CatalogTabProps) {
  const [localPlugins, setLocalPlugins] = useState<PluginResponse[]>(initialPlugins)
  const [rescanning, setRescanning] = useState(false)

  // Sync when parent plugins change
  useMemo(() => {
    setLocalPlugins(initialPlugins)
  }, [initialPlugins])

  const handleRescan = useCallback(async () => {
    setRescanning(true)
    try {
      await rescanPlugins()
      const data = await fetchPlugins()
      setLocalPlugins(data)
      onPluginsChanged()
    } catch {
      // ignore
    } finally {
      setRescanning(false)
    }
  }, [onPluginsChanged])

  const plugins = localPlugins
  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("all")
  const [sourceFilter, setSourceFilter] = useState("all")
  const [selectedPlugin, setSelectedPlugin] = useState<PluginResponse | null>(
    null,
  )

  const categories = useMemo(() => {
    const unique = new Set(plugins.map((p) => p.category))
    return Array.from(unique).sort()
  }, [plugins])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return plugins.filter((p) => {
      if (categoryFilter !== "all" && p.category !== categoryFilter)
        return false
      if (sourceFilter !== "all" && p.source !== sourceFilter) return false
      if (
        q &&
        !p.name.toLowerCase().includes(q) &&
        !p.display_name.toLowerCase().includes(q) &&
        !p.description.toLowerCase().includes(q) &&
        !p.tags.some((t) => t.toLowerCase().includes(q))
      )
        return false
      return true
    })
  }, [plugins, search, categoryFilter, sourceFilter])

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
          <Input
            placeholder="Search plugins..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {categories.map((cat) => (
              <SelectItem key={cat} value={cat}>
                {cat}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sourceFilter} onValueChange={setSourceFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Source" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Sources</SelectItem>
            <SelectItem value="builtin">Builtin</SelectItem>
            <SelectItem value="external">External</SelectItem>
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="sm"
          onClick={handleRescan}
          disabled={rescanning}
        >
          {rescanning ? (
            <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-1.5" />
          )}
          Rescan Plugins
        </Button>
      </div>

      {/* Plugin Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Plugin ID</TableHead>
              <TableHead>Category</TableHead>
              <TableHead className="text-center">Versions</TableHead>
              <TableHead>Source</TableHead>
              <TableHead className="text-center">In Pipeline</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-muted-foreground h-24 text-center">
                  No plugins found.
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((plugin) => (
                <TableRow
                  key={plugin.name}
                  className={`cursor-pointer ${selectedPlugin?.name === plugin.name ? "bg-muted/50" : ""}`}
                  onClick={() =>
                    setSelectedPlugin(
                      selectedPlugin?.name === plugin.name ? null : plugin,
                    )
                  }
                >
                  <TableCell className="font-medium">
                    {plugin.display_name}
                  </TableCell>
                  <TableCell>
                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
                      {plugin.name}
                    </code>
                  </TableCell>
                  <TableCell>{plugin.category}</TableCell>
                  <TableCell className="text-center">
                    {plugin.versions.length}
                  </TableCell>
                  <TableCell>{plugin.source}</TableCell>
                  <TableCell className="text-center">
                    {plugin.enabled !== null && plugin.enabled ? "✓" : ""}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Selected Plugin Detail */}
      {selectedPlugin && <CatalogDetail plugin={selectedPlugin} />}
    </div>
  )
}
