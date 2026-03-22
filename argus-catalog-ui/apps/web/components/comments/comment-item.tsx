"use client"

import { useState } from "react"
import { Bug, Lightbulb, MessageSquare, MoreHorizontal, Sparkles, Trash2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"

import type { CommentData } from "@/features/comments/api"
import { CommentEditor } from "./comment-editor"

type CommentItemProps = {
  comment: CommentData
  currentUser: string
  entityType: string
  entityId: string
  onReply: (parentId: number, content: string, contentPlain: string, category: string) => Promise<void>
  onDelete: (commentId: number) => Promise<void>
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
  currentUser,
  entityType,
  entityId,
  onReply,
  onDelete,
}: CommentItemProps) {
  const [showReplyEditor, setShowReplyEditor] = useState(false)

  const handleReply = async (content: string, contentPlain: string, category: string) => {
    await onReply(comment.id, content, contentPlain, category)
    setShowReplyEditor(false)
  }

  const isOwner = comment.author_name === currentUser
  const maxDepthIndent = Math.min(comment.depth, 4) // Cap indent at 4 levels

  return (
    <div style={{ marginLeft: `${maxDepthIndent * 24}px` }}>
      {comment.is_deleted ? (
        /* Deleted comment placeholder — still shows so child replies remain visible */
        <div className="border border-dashed rounded-lg p-3 mb-2 opacity-50">
          <p className="text-sm text-muted-foreground italic">This comment has been deleted.</p>
        </div>
      ) : (
      <div className="border rounded-lg p-3 mb-2">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {/* Avatar placeholder */}
            <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium text-primary">
              {comment.author_name.charAt(0).toUpperCase()}
            </div>
            <span className="text-sm font-medium">{comment.author_name}</span>
            <span className="text-xs text-muted-foreground">{timeAgo(comment.created_at)}</span>
            {comment.category === "suggestion" && (
              <span className="inline-flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full">
                <Lightbulb className="h-3 w-3" />
                Suggestion
              </span>
            )}
            {comment.category === "feature" && (
              <span className="inline-flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded-full">
                <Sparkles className="h-3 w-3" />
                Feature
              </span>
            )}
            {comment.category === "bug" && (
              <span className="inline-flex items-center gap-1 text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded-full">
                <Bug className="h-3 w-3" />
                Bug
              </span>
            )}
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
            {isOwner && (
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
          className="prose prose-sm max-w-none text-sm [&_pre]:overflow-x-auto [&_pre]:max-w-full [&_pre]:font-[D2Coding,monospace] [&_code]:font-[D2Coding,monospace]"
          dangerouslySetInnerHTML={{ __html: comment.content }}
        />
      </div>
      )}

      {/* Reply editor */}
      {showReplyEditor && (
        <div className="mb-2 ml-6">
          <CommentEditor
            onSubmit={handleReply}
            placeholder={`Reply to ${comment.author_name}...`}
            submitLabel="Reply"
            autoFocus
            onCancel={() => setShowReplyEditor(false)}
          />
        </div>
      )}

      {/* Nested replies */}
      {comment.replies?.map((reply) => (
        <CommentItem
          key={reply.id}
          comment={reply}
          currentUser={currentUser}
          entityType={entityType}
          entityId={entityId}
          onReply={onReply}
          onDelete={onDelete}
        />
      ))}
    </div>
  )
}
