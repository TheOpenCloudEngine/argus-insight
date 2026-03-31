"use client"

import { useMemo } from "react"
import dynamic from "next/dynamic"
import yaml from "js-yaml"

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false })

interface YamlViewerProps {
  /** JSON object to display as YAML */
  data: unknown
  /** Height of the editor (CSS value) */
  height?: string
}

/**
 * Read-only Monaco-based YAML viewer for Spec, Status, and other JSON objects.
 * Converts JSON to YAML with syntax highlighting, light theme, D2Coding font.
 */
export function YamlViewer({ data, height = "300px" }: YamlViewerProps) {
  const yamlText = useMemo(() => {
    if (data == null) return ""
    try {
      return yaml.dump(data, { indent: 2, lineWidth: -1, noRefs: true })
    } catch {
      return JSON.stringify(data, null, 2)
    }
  }, [data])

  if (!yamlText) return null

  return (
    <div className="rounded-md border overflow-hidden">
      <MonacoEditor
        height={height}
        language="yaml"
        theme="light"
        value={yamlText}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: "var(--font-d2coding), 'D2Coding', monospace",
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          wordWrap: "on",
          tabSize: 2,
          automaticLayout: true,
          renderLineHighlight: "none",
          padding: { top: 8, bottom: 8 },
          scrollbar: { verticalScrollbarSize: 8 },
        }}
      />
    </div>
  )
}
