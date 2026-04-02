"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  ArrowLeft,
  Loader2,
  MessageSquare,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import { useAuth } from "@/features/auth"
import {
  changeVocAssignee,
  changeVocPriority,
  changeVocStatus,
  createVocComment,
  deleteVocComment,
  fetchVocComments,
  fetchVocIssue,
} from "@/features/voc/api"
import type { VocComment, VocIssue } from "@/features/voc/types"
import { CommentEditor } from "@/components/comments/comment-editor"
import { CommentItem, type CommentItemData } from "@/components/comments/comment-item"

// ── Helpers ───────────────────────────────────────────────

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  open: { label: "Open", color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" },
  in_progress: { label: "In Progress", color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200" },
  resolved: { label: "Resolved", color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" },
  rejected: { label: "Rejected", color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200" },
  closed: { label: "Closed", color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
}

const PRIORITY_LABELS: Record<string, { label: string; color: string }> = {
  critical: { label: "Critical", color: "bg-red-100 text-red-800" },
  high: { label: "High", color: "bg-orange-100 text-orange-800" },
  medium: { label: "Medium", color: "bg-blue-50 text-blue-700" },
  low: { label: "Low", color: "bg-gray-50 text-gray-600" },
}

const CATEGORY_LABELS: Record<string, string> = {
  resource_request: "Resource Request",
  service_issue: "Service Issue",
  feature_request: "Feature Request",
  account: "Account",
  general: "General",
}

function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString()
}

// ── Component ─────────────────────────────────────────────

interface VocDetailProps {
  issueId: number
}

export function VocDetail({ issueId }: VocDetailProps) {
  const router = useRouter()
  const { user } = useAuth()
  const [issue, setIssue] = useState<VocIssue | null>(null)
  const [comments, setComments] = useState<VocComment[]>([])
  const [loading, setLoading] = useState(true)

  const isAdmin = user?.is_admin ?? false
  const currentUserId = user ? parseInt(user.sub) : 0

  const load = useCallback(async () => {
    try {
      const [iss, cmts] = await Promise.all([
        fetchVocIssue(issueId),
        fetchVocComments(issueId),
      ])
      setIssue(iss)
      setComments(cmts)
    } catch (e) {
      console.error("Failed to load VOC issue:", e)
    } finally {
      setLoading(false)
    }
  }, [issueId])

  useEffect(() => { load() }, [load])

  const handleStatusChange = async (status: string) => {
    const updated = await changeVocStatus(issueId, status)
    setIssue(updated)
    const cmts = await fetchVocComments(issueId)
    setComments(cmts)
  }

  const handlePriorityChange = async (priority: string) => {
    const updated = await changeVocPriority(issueId, priority)
    setIssue(updated)
    const cmts = await fetchVocComments(issueId)
    setComments(cmts)
  }

  const handleAssignToMe = async () => {
    if (!user) return
    const updated = await changeVocAssignee(issueId, parseInt(user.sub), user.username)
    setIssue(updated)
    const cmts = await fetchVocComments(issueId)
    setComments(cmts)
  }

  const handlePostComment = async (body: string, bodyPlain: string) => {
    await createVocComment(issueId, body, bodyPlain)
    const cmts = await fetchVocComments(issueId)
    setComments(cmts)
  }

  const handleReplyComment = async (parentId: number, body: string, bodyPlain: string) => {
    await createVocComment(issueId, body, bodyPlain, parentId)
    const cmts = await fetchVocComments(issueId)
    setComments(cmts)
  }

  const handleDeleteComment = async (commentId: number) => {
    await deleteVocComment(issueId, commentId)
    const cmts = await fetchVocComments(issueId)
    setComments(cmts)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!issue) {
    return (
      <div className="text-center py-20 text-muted-foreground">Issue not found.</div>
    )
  }

  const st = STATUS_LABELS[issue.status] ?? { label: issue.status, color: "" }
  const pr = PRIORITY_LABELS[issue.priority] ?? { label: issue.priority, color: "" }
  // Build flat comment list for threaded rendering
  const topLevelComments = comments.filter((c) => !c.parent_id)
  const commentItems: CommentItemData[] = comments.map((c) => ({
    id: c.id,
    issue_id: c.issue_id,
    parent_id: c.parent_id,
    author_user_id: c.author_user_id,
    author_username: c.author_username,
    body: c.body,
    body_plain: c.body_plain,
    is_system: c.is_system,
    is_deleted: c.is_deleted,
    created_at: c.created_at,
    updated_at: c.updated_at,
  }))

  return (
    <div className="space-y-6">
      {/* Back */}
      <Button variant="ghost" size="sm" onClick={() => router.push("/dashboard/voc")}>
        <ArrowLeft className="mr-1 h-4 w-4" /> Back to Issues
      </Button>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        {/* Main content */}
        <div className="space-y-6">
          {/* Title & description */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-muted-foreground font-mono text-sm">#{issue.id}</span>
              <h1 className="text-xl font-semibold">{issue.title}</h1>
            </div>
            <div
              className="prose prose-sm max-w-none border rounded-lg p-4 text-sm [&_p]:my-2 [&_pre]:overflow-x-auto [&_pre]:font-[D2Coding,monospace] [&_code]:font-[D2Coding,monospace]"
              dangerouslySetInnerHTML={{ __html: issue.description }}
            />
          </div>

          {/* Resource detail */}
          {issue.resource_detail && (
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">Resource Request</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Type</span>
                  <p className="font-medium">{String(issue.resource_detail.resource_type ?? "—")}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Current</span>
                  <p className="font-medium">{String(issue.resource_detail.current ?? "—")}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Requested</span>
                  <p className="font-medium">{String(issue.resource_detail.requested ?? "—")}</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Comments */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-muted-foreground" />
              <h3 className="text-base font-medium">
                Comments{" "}
                {comments.length > 0 && (
                  <span className="text-muted-foreground">({comments.length})</span>
                )}
              </h3>
            </div>

            {/* Comment list */}
            <div className="space-y-1">
              {topLevelComments.map((c) => (
                <CommentItem
                  key={c.id}
                  comment={commentItems.find((ci) => ci.id === c.id)!}
                  currentUserId={currentUserId}
                  isAdmin={isAdmin}
                  onReply={handleReplyComment}
                  onDelete={handleDeleteComment}
                  childComments={commentItems}
                />
              ))}
            </div>

            {/* New comment editor */}
            <CommentEditor onSubmit={handlePostComment} placeholder="Write a comment..." />
          </div>
        </div>

        {/* Sidebar details */}
        <div className="space-y-4">
          <Card>
            <CardContent className="space-y-3 pt-4">
              {/* Status */}
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Status</span>
                {isAdmin ? (
                  <Select value={issue.status} onValueChange={handleStatusChange}>
                    <SelectTrigger className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="in_progress">In Progress</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                      <SelectItem value="rejected">Rejected</SelectItem>
                      <SelectItem value="closed">Closed</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Badge className={st.color}>{st.label}</Badge>
                )}
              </div>

              {/* Priority */}
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Priority</span>
                {isAdmin ? (
                  <Select value={issue.priority} onValueChange={handlePriorityChange}>
                    <SelectTrigger className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="critical">Critical</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Badge className={pr.color}>{pr.label}</Badge>
                )}
              </div>

              {/* Category */}
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Category</span>
                <p className="text-sm">{CATEGORY_LABELS[issue.category] ?? issue.category}</p>
              </div>

              {/* Assignee */}
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Assignee</span>
                <p className="text-sm">{issue.assignee_username ?? "Unassigned"}</p>
                {isAdmin && !issue.assignee_user_id && (
                  <Button variant="outline" size="sm" className="text-xs w-full" onClick={handleAssignToMe}>
                    Assign to me
                  </Button>
                )}
              </div>

              {/* Author */}
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">Author</span>
                <p className="text-sm">{issue.author_username ?? "—"}</p>
              </div>

              {/* Context */}
              {(issue.workspace_name || issue.service_name) && (
                <div className="space-y-1 border-t pt-3">
                  <span className="text-xs text-muted-foreground">Context</span>
                  {issue.workspace_name && (
                    <p className="text-sm">Workspace: {issue.workspace_name}</p>
                  )}
                  {issue.service_name && (
                    <p className="text-sm">Service: {issue.service_name}</p>
                  )}
                </div>
              )}

              {/* Timestamps */}
              <div className="space-y-1 border-t pt-3">
                <p className="text-xs text-muted-foreground">Created: {formatDateTime(issue.created_at)}</p>
                {issue.resolved_at && (
                  <p className="text-xs text-muted-foreground">Resolved: {formatDateTime(issue.resolved_at)}</p>
                )}
                {issue.closed_at && (
                  <p className="text-xs text-muted-foreground">Closed: {formatDateTime(issue.closed_at)}</p>
                )}
              </div>

            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
