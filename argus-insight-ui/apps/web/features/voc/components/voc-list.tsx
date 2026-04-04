"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  AlertCircle,
  ArrowUpDown,
  CircleDot,
  Loader2,
  MessageSquare,
  Plus,
  Search,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
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

import { useAuth } from "@/features/auth"
import { fetchVocIssues } from "@/features/voc/api"
import type { PaginatedVocIssues, VocIssue } from "@/features/voc/types"
import { VocCreateDialog } from "./voc-create-dialog"

// ── Helpers ───────────────────────────────────────────────

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  open: { label: "Open", color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" },
  in_progress: { label: "In Progress", color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200" },
  resolved: { label: "Resolved", color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" },
  rejected: { label: "Rejected", color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200" },
  closed: { label: "Closed", color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
}

const PRIORITY_LABELS: Record<string, { label: string; color: string }> = {
  critical: { label: "Critical", color: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" },
  high: { label: "High", color: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200" },
  medium: { label: "Medium", color: "bg-blue-50 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300" },
  low: { label: "Low", color: "bg-gray-50 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
}

const CATEGORY_LABELS: Record<string, string> = {
  resource_request: "Resource",
  service_issue: "Service",
  feature_request: "Feature",
  account: "Account",
  general: "General",
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return `${Math.floor(days / 30)}mo ago`
}

// ── Component ─────────────────────────────────────────────

export function VocList() {
  const router = useRouter()
  const { user } = useAuth()
  const [data, setData] = useState<PaginatedVocIssues | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [filterStatus, setFilterStatus] = useState("all")
  const [filterCategory, setFilterCategory] = useState("all")
  const [search, setSearch] = useState("")
  const [createOpen, setCreateOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await fetchVocIssues({
        page,
        page_size: 10,
        status: filterStatus !== "all" ? filterStatus : undefined,
        category: filterCategory !== "all" ? filterCategory : undefined,
        search: search || undefined,
      })
      setData(result)
    } catch (e) {
      console.error("Failed to load VOC issues:", e)
    } finally {
      setLoading(false)
    }
  }, [page, filterStatus, filterCategory, search])

  useEffect(() => { load() }, [load])

  const totalPages = data ? Math.ceil(data.total / 10) : 0

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-end">
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" /> New Issue
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Select value={filterStatus} onValueChange={(v) => { setFilterStatus(v); setPage(1) }}>
          <SelectTrigger className="h-8 w-[130px] text-xs">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
            <SelectItem value="closed">Closed</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filterCategory} onValueChange={(v) => { setFilterCategory(v); setPage(1) }}>
          <SelectTrigger className="h-8 w-[130px] text-xs">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Category</SelectItem>
            <SelectItem value="resource_request">Resource</SelectItem>
            <SelectItem value="service_issue">Service</SelectItem>
            <SelectItem value="feature_request">Feature</SelectItem>
            <SelectItem value="account">Account</SelectItem>
            <SelectItem value="general">General</SelectItem>
          </SelectContent>
        </Select>

        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search issues..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { setPage(1); load() } }}
            className="h-8 pl-8 text-xs"
          />
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">
          No issues found.
        </div>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[50px]">#</TableHead>
                <TableHead>Title</TableHead>
                <TableHead className="w-[90px]">Category</TableHead>
                <TableHead className="w-[80px]">Priority</TableHead>
                <TableHead className="w-[100px]">Status</TableHead>
                <TableHead className="w-[80px]">Author</TableHead>
                <TableHead className="w-[80px]">Age</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((issue) => {
                const st = STATUS_LABELS[issue.status] ?? { label: issue.status, color: "" }
                const pr = PRIORITY_LABELS[issue.priority] ?? { label: issue.priority, color: "" }
                return (
                  <TableRow
                    key={issue.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/dashboard/voc/${issue.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {issue.id}
                    </TableCell>
                    <TableCell>
                      <div>
                        <span className="text-sm font-medium">{issue.title}</span>
                        {(issue.workspace_name || issue.service_name) && (
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {issue.workspace_name}
                            {issue.service_name && ` / ${issue.service_name}`}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs">{CATEGORY_LABELS[issue.category] ?? issue.category}</span>
                    </TableCell>
                    <TableCell>
                      <Badge className={`text-[10px] ${pr.color}`}>{pr.label}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={`text-[10px] ${st.color}`}>{st.label}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">{issue.author_username ?? "—"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      <div className="flex items-center gap-1.5">
                        {timeAgo(issue.created_at)}
                        {issue.comment_count > 0 && (
                          <span className="inline-flex items-center gap-0.5 text-muted-foreground">
                            <MessageSquare className="h-3 w-3" />
                            {issue.comment_count}
                          </span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <Button
              key={p}
              variant={p === page ? "default" : "outline"}
              size="sm"
              className="w-8 h-8 p-0"
              onClick={() => setPage(p)}
            >
              {p}
            </Button>
          ))}
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {/* Create dialog */}
      <VocCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => { setCreateOpen(false); setPage(1); load() }}
      />
    </div>
  )
}
