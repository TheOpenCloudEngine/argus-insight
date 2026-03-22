"use client"

import { useCallback, useEffect, useState } from "react"
import { MessageSquare } from "lucide-react"

import { Button } from "@workspace/ui/components/button"

import {
  fetchComments,
  createComment,
  deleteComment,
  type CommentData,
  type PaginatedComments,
} from "@/features/comments/api"
import { useAuth } from "@/features/auth"
import { CommentEditor } from "./comment-editor"
import { CommentItem } from "./comment-item"

type CommentSectionProps = {
  /** Entity type (e.g. "dataset", "model", "glossary"). */
  entityType: string
  /** Entity identifier (e.g. dataset ID, model name). */
  entityId: string
  /** Number of top-level comments per page (default: 10). */
  pageSize?: number
}

export function CommentSection({
  entityType,
  entityId,
  pageSize = 5,
}: CommentSectionProps) {
  const { user } = useAuth()
  const currentUser = user?.username ?? "anonymous"
  const [comments, setComments] = useState<CommentData[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const totalPages = Math.ceil(total / pageSize)

  const load = useCallback(async (p: number) => {
    try {
      setLoading(true)
      const data: PaginatedComments = await fetchComments(entityType, entityId, p, pageSize)
      setComments(data.items)
      setTotal(data.total)
      setPage(p)
    } catch (err) {
      console.error("Failed to load comments:", err)
    } finally {
      setLoading(false)
    }
  }, [entityType, entityId, pageSize])

  useEffect(() => {
    load(1)
  }, [load])

  const handlePost = useCallback(async (
    content: string, contentPlain: string, category: string,
  ) => {
    await createComment({
      entity_type: entityType,
      entity_id: entityId,
      content,
      content_plain: contentPlain,
      category,
      author_name: currentUser,
    })
    await load(1)
  }, [entityType, entityId, currentUser, load])

  const handleReply = useCallback(async (
    parentId: number, content: string, contentPlain: string, category: string,
  ) => {
    await createComment({
      entity_type: entityType,
      entity_id: entityId,
      parent_id: parentId,
      content,
      content_plain: contentPlain,
      category,
      author_name: currentUser,
    })
    // Reload current page to show new reply
    await load(page)
  }, [entityType, entityId, currentUser, load, page])

  const handleDelete = useCallback(async (commentId: number) => {
    await deleteComment(commentId)
    await load(page)
  }, [load, page])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <MessageSquare className="h-5 w-5 text-muted-foreground" />
        <h3 className="text-base font-medium">
          Comments {total > 0 && <span className="text-muted-foreground">({total})</span>}
        </h3>
      </div>

      {/* Editor */}
      <CommentEditor onSubmit={handlePost} />

      {/* Comment list */}
      {loading ? (
        <p className="text-sm text-muted-foreground text-center py-8">Loading comments...</p>
      ) : comments.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">No comments yet. Be the first!</p>
      ) : (
        <div className="space-y-1">
          {comments.map((c) => (
            <CommentItem
              key={c.id}
              comment={c}
              currentUser={currentUser}
              entityType={entityType}
              entityId={entityId}
              onReply={handleReply}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => load(page - 1)}
          >
            Previous
          </Button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <Button
              key={p}
              variant={p === page ? "default" : "outline"}
              size="sm"
              className="w-8 h-8 p-0"
              onClick={() => load(p)}
            >
              {p}
            </Button>
          ))}
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => load(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
