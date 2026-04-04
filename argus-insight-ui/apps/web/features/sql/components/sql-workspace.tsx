"use client"

import React, { useCallback, useRef, useState } from "react"
import { TooltipProvider } from "@workspace/ui/components/tooltip"
import { DatasourceSidebar } from "./datasource-sidebar"
import { ResultPanel } from "./result-panel"
import { SqlEditorPanel } from "./sql-editor-panel"

// ---------------------------------------------------------------------------
// Resizable split helpers
// ---------------------------------------------------------------------------

function VerticalSplitter({ onDrag }: { onDrag: (deltaX: number) => void }) {
  const dragging = useRef(false)
  const lastX = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true
    lastX.current = e.clientX

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current) return
      const dx = ev.clientX - lastX.current
      lastX.current = ev.clientX
      onDrag(dx)
    }
    const onMouseUp = () => {
      dragging.current = false
      document.removeEventListener("mousemove", onMouseMove)
      document.removeEventListener("mouseup", onMouseUp)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
    document.addEventListener("mousemove", onMouseMove)
    document.addEventListener("mouseup", onMouseUp)
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
  }, [onDrag])

  return (
    <div
      onMouseDown={onMouseDown}
      className="w-1 shrink-0 cursor-col-resize bg-border hover:bg-primary/30 active:bg-primary/50 transition-colors"
    />
  )
}

function HorizontalSplitter({ onDrag }: { onDrag: (deltaY: number) => void }) {
  const dragging = useRef(false)
  const lastY = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true
    lastY.current = e.clientY

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current) return
      const dy = ev.clientY - lastY.current
      lastY.current = ev.clientY
      onDrag(dy)
    }
    const onMouseUp = () => {
      dragging.current = false
      document.removeEventListener("mousemove", onMouseMove)
      document.removeEventListener("mouseup", onMouseUp)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
    document.addEventListener("mousemove", onMouseMove)
    document.addEventListener("mouseup", onMouseUp)
    document.body.style.cursor = "row-resize"
    document.body.style.userSelect = "none"
  }, [onDrag])

  return (
    <div
      onMouseDown={onMouseDown}
      className="h-1 shrink-0 cursor-row-resize bg-border hover:bg-primary/30 active:bg-primary/50 transition-colors"
    />
  )
}

// ---------------------------------------------------------------------------
// Main workspace
// ---------------------------------------------------------------------------

export function SqlWorkspace() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [sidebarWidth, setSidebarWidth] = useState(260)
  const [editorRatio, setEditorRatio] = useState(0.55) // top = 55%

  const handleVerticalDrag = useCallback((dx: number) => {
    setSidebarWidth((prev) => Math.max(180, Math.min(500, prev + dx)))
  }, [])

  const handleHorizontalDrag = useCallback((dy: number) => {
    const container = containerRef.current
    if (!container) return
    const totalHeight = container.getBoundingClientRect().height
    if (totalHeight <= 0) return
    setEditorRatio((prev) => {
      const next = prev + dy / totalHeight
      return Math.max(0.2, Math.min(0.8, next))
    })
  }, [])

  return (
    <TooltipProvider delayDuration={200}>
      <div ref={containerRef} className="flex h-full min-h-0 w-full min-w-0 flex-1 overflow-hidden">
        {/* Left: Datasource tree */}
        <div style={{ width: sidebarWidth }} className="shrink-0 h-full min-h-0 overflow-hidden">
          <DatasourceSidebar />
        </div>

        <VerticalSplitter onDrag={handleVerticalDrag} />

        {/* Right: Editor + Results */}
        <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
          {/* Top: SQL Editor */}
          <div style={{ flex: `${editorRatio} 1 0%` }} className="min-h-[120px] overflow-hidden">
            <SqlEditorPanel />
          </div>

          <HorizontalSplitter onDrag={handleHorizontalDrag} />

          {/* Bottom: Results */}
          <div style={{ flex: `${1 - editorRatio} 1 0%` }} className="min-h-[100px] overflow-hidden">
            <ResultPanel />
          </div>
        </div>
      </div>

      {/* Dialogs (placeholder for future) */}
    </TooltipProvider>
  )
}
