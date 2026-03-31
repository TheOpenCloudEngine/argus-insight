"use client"

import { useCallback, useState } from "react"
import { Copy, Save } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import type { K8sResourceItem } from "../types"

interface YamlEditorProps {
  resource: K8sResourceItem
  onSave?: (body: object) => Promise<void>
}

/**
 * YAML viewer/editor using a textarea (lightweight alternative to Monaco).
 * Displays the resource as formatted JSON (YAML support can be added later
 * with a js-yaml dependency).
 */
export function YamlEditor({ resource, onSave }: YamlEditorProps) {
  const initialText = JSON.stringify(resource, null, 2)
  const [text, setText] = useState(initialText)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const isModified = text !== initialText

  const handleSave = useCallback(async () => {
    if (!onSave) return
    setError(null)
    setSaving(true)
    try {
      const parsed = JSON.parse(text)
      await onSave(parsed)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }, [text, onSave])

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [text])

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {onSave && (
            <Button
              variant="outline"
              size="sm"
              className="h-8"
              disabled={!isModified || saving}
              onClick={handleSave}
            >
              <Save className="h-3.5 w-3.5 mr-1" />
              {saving ? "Saving..." : "Save"}
            </Button>
          )}
          <Button variant="ghost" size="sm" className="h-8" onClick={handleCopy}>
            <Copy className="h-3.5 w-3.5 mr-1" />
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
        {isModified && (
          <span className="text-xs text-amber-500">Modified</span>
        )}
      </div>

      {error && (
        <div className="text-xs text-destructive bg-destructive/10 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full min-h-[500px] bg-zinc-950 text-zinc-100 font-mono text-xs leading-5 p-3 rounded-md border border-zinc-800 resize-y focus:outline-none focus:ring-1 focus:ring-blue-500"
        spellCheck={false}
        readOnly={!onSave}
      />
    </div>
  )
}
