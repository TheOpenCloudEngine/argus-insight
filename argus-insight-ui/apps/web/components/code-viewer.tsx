"use client"

import { useRef } from "react"

type CodeViewerProps = {
  content: string
  maxHeight?: string
}

export function CodeViewer({ content, maxHeight = "300px" }: CodeViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const lines = content ? content.split("\n") : ["(empty)"]
  const gutterWidth = String(lines.length).length

  return (
    <div
      ref={containerRef}
      className="overflow-auto rounded-md border bg-muted text-xs font-mono leading-relaxed"
      style={{ maxHeight }}
    >
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((line, i) => (
            <tr key={i} className="hover:bg-muted-foreground/5">
              <td className="sticky left-0 select-none bg-muted px-2 py-0 text-right text-muted-foreground/50 border-r border-border/50" style={{ minWidth: `${gutterWidth + 2}ch` }}>
                {i + 1}
              </td>
              <td className="px-3 py-0 whitespace-pre">
                {line || " "}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
