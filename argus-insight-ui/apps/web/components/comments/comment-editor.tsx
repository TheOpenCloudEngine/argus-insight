"use client"

import { useCallback, useState } from "react"
import { useEditor, EditorContent } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import Link from "@tiptap/extension-link"
import Placeholder from "@tiptap/extension-placeholder"
import {
  Bold, Code, Heading3, Italic, Link2, List, ListOrdered,
  Minus, Quote, Redo, RemoveFormatting, Strikethrough, Undo,
} from "lucide-react"

import { Button } from "@workspace/ui/components/button"

type CommentEditorProps = {
  onSubmit: (content: string, contentPlain: string) => Promise<void>
  placeholder?: string
  submitLabel?: string
  autoFocus?: boolean
  onCancel?: () => void
  /** Hide the footer bar (submit/cancel buttons). Useful when embedded in a form with its own submit. */
  hideFooter?: boolean
  /** Called on every content change with (html, plain, isEmpty). */
  onChange?: (html: string, plain: string, isEmpty: boolean) => void
  /** Minimum height of the editor area (default: "80px"). */
  minHeight?: string
}

function ToolbarButton({
  onClick,
  active,
  title,
  children,
}: {
  onClick: () => void
  active?: boolean
  title?: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`p-1 rounded hover:bg-muted transition-colors ${
        active ? "bg-muted text-foreground" : "text-muted-foreground"
      }`}
    >
      {children}
    </button>
  )
}

export function CommentEditor({
  onSubmit,
  placeholder = "Write a comment...",
  submitLabel = "Post",
  autoFocus = false,
  onCancel,
  hideFooter = false,
  onChange,
  minHeight = "80px",
}: CommentEditorProps) {
  const [submitting, setSubmitting] = useState(false)
  const [isEmpty, setIsEmpty] = useState(true)

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder }),
    ],
    autofocus: autoFocus,
    editorProps: {
      attributes: {
        class: `prose prose-sm max-w-none px-3 py-2 text-sm focus:outline-none overflow-x-auto [&_pre]:overflow-x-auto [&_pre]:max-w-full [&_pre]:font-[D2Coding,monospace] [&_code]:font-[D2Coding,monospace] [&_code]:break-all`,
        style: `min-height: ${minHeight}`,
      },
    },
    onUpdate: ({ editor: e }) => {
      setIsEmpty(e.isEmpty)
      onChange?.(e.getHTML(), e.getText(), e.isEmpty)
    },
  })

  const handleSubmit = useCallback(async () => {
    if (!editor || editor.isEmpty) return
    setSubmitting(true)
    try {
      const html = editor.getHTML()
      const plain = editor.getText()
      await onSubmit(html, plain)
      editor.commands.clearContent()
      setIsEmpty(true)
    } finally {
      setSubmitting(false)
    }
  }, [editor, onSubmit])

  if (!editor) return null

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-0.5 px-2 py-1 border-b bg-muted/30 flex-wrap">
        <ToolbarButton title="Bold" onClick={() => editor.chain().focus().toggleBold().run()} active={editor.isActive("bold")}>
          <Bold className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Italic" onClick={() => editor.chain().focus().toggleItalic().run()} active={editor.isActive("italic")}>
          <Italic className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Strikethrough" onClick={() => editor.chain().focus().toggleStrike().run()} active={editor.isActive("strike")}>
          <Strikethrough className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Inline Code" onClick={() => editor.chain().focus().toggleCode().run()} active={editor.isActive("code")}>
          <Code className="h-3.5 w-3.5" />
        </ToolbarButton>
        <div className="w-px h-4 bg-border mx-1" />
        <ToolbarButton title="Heading 3" onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} active={editor.isActive("heading", { level: 3 })}>
          <Heading3 className="h-3.5 w-3.5" />
        </ToolbarButton>
        <div className="w-px h-4 bg-border mx-1" />
        <ToolbarButton title="Bullet List" onClick={() => editor.chain().focus().toggleBulletList().run()} active={editor.isActive("bulletList")}>
          <List className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Ordered List" onClick={() => editor.chain().focus().toggleOrderedList().run()} active={editor.isActive("orderedList")}>
          <ListOrdered className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Blockquote" onClick={() => editor.chain().focus().toggleBlockquote().run()} active={editor.isActive("blockquote")}>
          <Quote className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Code Block" onClick={() => editor.chain().focus().toggleCodeBlock().run()} active={editor.isActive("codeBlock")}>
          <span className="text-[10px] font-mono font-bold leading-none">{"{}"}</span>
        </ToolbarButton>
        <div className="w-px h-4 bg-border mx-1" />
        <ToolbarButton title="Horizontal Rule" onClick={() => editor.chain().focus().setHorizontalRule().run()}>
          <Minus className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Link" onClick={() => { const url = window.prompt("Enter URL:"); if (url) editor.chain().focus().setLink({ href: url }).run() }} active={editor.isActive("link")}>
          <Link2 className="h-3.5 w-3.5" />
        </ToolbarButton>
        <div className="w-px h-4 bg-border mx-1" />
        <ToolbarButton title="Clear Formatting" onClick={() => editor.chain().focus().unsetAllMarks().clearNodes().run()}>
          <RemoveFormatting className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Undo" onClick={() => editor.chain().focus().undo().run()}>
          <Undo className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Redo" onClick={() => editor.chain().focus().redo().run()}>
          <Redo className="h-3.5 w-3.5" />
        </ToolbarButton>
      </div>

      {/* Editor */}
      <EditorContent editor={editor} />

      {/* Footer */}
      {!hideFooter && (
        <div className="flex items-center justify-end px-3 py-2 border-t bg-muted/10 gap-2">
          {onCancel && (
            <Button variant="ghost" size="sm" onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
          )}
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={submitting || isEmpty}
          >
            {submitting ? "Posting..." : submitLabel}
          </Button>
        </div>
      )}
    </div>
  )
}
