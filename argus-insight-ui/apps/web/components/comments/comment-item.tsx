"use client"

import { useState } from "react"
import { Bot, MessageSquare, MoreHorizontal, Trash2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"

import { CommentEditor } from "./comment-editor"

export type CommentItemData = {
  id: number
  issue_id: number
  parent_id: number | null
  author_user_id: number
  author_username: string | null
  body: string
  body_plain: string | null
  is_system: boolean
  is_deleted: boolean
  created_at: string
  updated_at: string
}

type CommentItemProps = {
  comment: CommentItemData
  currentUserId: number
  isAdmin: boolean
  onReply: (parentId: number, body: string, bodyPlain: string) => Promise<void>
  onDelete: (commentId: number) => Promise<void>
  depth?: number
  childComments?: CommentItemData[]
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
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

export function CommentItem({
  comment,
  currentUserId,
  isAdmin,
  onReply,
  onDelete,
  depth = 0,
  childComments = [],
}: CommentItemProps) {
  const [showReplyEditor, setShowReplyEditor] = useState(false)

  const handleReply = async (content: string, contentPlain: string) => {
    await onReply(comment.id, content, contentPlain)
    setShowReplyEditor(false)
  }

  const canDelete = isAdmin
  const maxDepthIndent = Math.min(depth, 4)
  const author = comment.author_username ?? "Unknown"

  // Find direct children of this comment
  const directChildren = childComments.filter((c) => c.parent_id === comment.id)

  if (comment.is_deleted) {
    return (
      <div style={{ marginLeft: `${maxDepthIndent * 24}px` }}>
        <div className="border border-dashed rounded-lg p-3 mb-2 opacity-50">
          <p className="text-sm text-muted-foreground italic">This comment has been deleted.</p>
        </div>
        {directChildren.map((child) => (
          <CommentItem
            key={child.id}
            comment={child}
            currentUserId={currentUserId}
            isAdmin={isAdmin}
            onReply={onReply}
            onDelete={onDelete}
            depth={depth + 1}
            childComments={childComments}
          />
        ))}
      </div>
    )
  }

  if (comment.is_system) {
    return (
      <div style={{ marginLeft: `${maxDepthIndent * 24}px` }}>
        <div className="flex items-center gap-2 py-2 px-3 mb-1 text-xs text-muted-foreground">
          <Bot className="h-3.5 w-3.5 shrink-0" />
          <span
            className="prose prose-sm max-w-none [&_p]:m-0"
            dangerouslySetInnerHTML={{ __html: comment.body }}
          />
          <span className="shrink-0">{timeAgo(comment.created_at)}</span>
        </div>
      </div>
    )
  }

  return (
    <div style={{ marginLeft: `${maxDepthIndent * 24}px` }}>
      <div className="border rounded-lg p-3 mb-2">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium text-primary">
              {author.charAt(0).toUpperCase()}
            </div>
            <span className="text-sm font-medium">{author}</span>
            <span className="text-xs text-muted-foreground">{timeAgo(comment.created_at)}</span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-muted-foreground"
              onClick={() => setShowReplyEditor(!showReplyEditor)}
            >
              <MessageSquare className="h-3.5 w-3.5 mr-1" />
              Reply
            </Button>
            {canDelete && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                    <MoreHorizontal className="h-3.5 w-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    className="text-destructive"
                    onClick={() => onDelete(comment.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>

        {/* Content */}
        <div
          className="prose prose-sm max-w-none text-sm [&_p]:my-2 [&_pre]:overflow-x-auto [&_pre]:max-w-full [&_pre]:font-[D2Coding,monospace] [&_code]:font-[D2Coding,monospace]"
          dangerouslySetInnerHTML={{ __html: comment.body }}
        />
      </div>

      {/* Reply editor */}
      {showReplyEditor && (
        <div className="mb-2 ml-6">
          <CommentEditor
            onSubmit={handleReply}
            placeholder={`Reply to ${author}...`}
            submitLabel="Reply"
            autoFocus
            onCancel={() => setShowReplyEditor(false)}
          />
        </div>
      )}

      {/* Nested replies */}
      {directChildren.map((child) => (
        <CommentItem
          key={child.id}
          comment={child}
          currentUserId={currentUserId}
          isAdmin={isAdmin}
          onReply={onReply}
          onDelete={onDelete}
          depth={depth + 1}
          childComments={childComments}
        />
      ))}
    </div>
  )
}
