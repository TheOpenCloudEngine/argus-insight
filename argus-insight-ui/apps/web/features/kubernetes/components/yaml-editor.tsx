"use client"

import { useCallback, useMemo, useRef, useState } from "react"
import { Copy, Save } from "lucide-react"
import dynamic from "next/dynamic"
import yaml from "js-yaml"
import { Button } from "@workspace/ui/components/button"
import type { K8sResourceItem } from "../types"

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false })

interface YamlEditorProps {
  resource: K8sResourceItem
  onSave?: (body: object) => Promise<void>
}

/**
 * YAML viewer/editor using Monaco Editor with YAML syntax highlighting.
 * Converts the K8s resource JSON to YAML for display, and back to JSON for save.
 */
export function YamlEditor({ resource, onSave }: YamlEditorProps) {
  const initialYaml = useMemo(() => {
    try {
      return yaml.dump(resource, { indent: 2, lineWidth: -1, noRefs: true })
    } catch {
      return JSON.stringify(resource, null, 2)
    }
  }, [resource])

  const [text, setText] = useState(initialYaml)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const editorRef = useRef<unknown>(null)

  const isModified = text !== initialYaml

  const handleEditorDidMount = useCallback((editor: unknown) => {
    editorRef.current = editor
  }, [])

  const handleSave = useCallback(async () => {
    if (!onSave) return
    setError(null)
    setSaving(true)
    try {
      const parsed = yaml.load(text) as object
      await onSave(parsed)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }, [text, onSave])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const ta = document.createElement("textarea")
      ta.value = text
      ta.style.position = "fixed"
      ta.style.opacity = "0"
      document.body.appendChild(ta)
      ta.select()
      document.execCommand("copy")
      document.body.removeChild(ta)
    }
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

      <div className="rounded-md border overflow-hidden">
        <MonacoEditor
          height="calc(100vh - 320px)"
          language="yaml"
          theme="light"
          value={text}
          onChange={(value) => setText(value ?? "")}
          onMount={handleEditorDidMount}
          options={{
            readOnly: !onSave,
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "var(--font-d2coding), 'D2Coding', monospace",
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            tabSize: 2,
            automaticLayout: true,
            renderLineHighlight: "line",
            padding: { top: 8, bottom: 8 },
          }}
        />
      </div>
    </div>
  )
}
