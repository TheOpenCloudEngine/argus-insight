"use client"

import { useEffect, useRef, useState } from "react"
import { Download, Pause, Play, Trash2 } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { usePodLogs } from "../hooks/use-pod-logs"

interface PodLogViewerProps {
  name: string
  namespace: string
  containers: string[]
}

export function PodLogViewer({ name, namespace, containers }: PodLogViewerProps) {
  const [container, setContainer] = useState(containers[0] || "")
  const [follow, setFollow] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const logRef = useRef<HTMLDivElement>(null)

  const {
    lines,
    loading,
    error,
    streaming,
    startStreaming,
    stopStreaming,
    clearLogs,
  } = usePodLogs(name, namespace, {
    container: container || undefined,
    tailLines: 500,
    follow,
  })

  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [lines, autoScroll])

  const handleDownload = () => {
    const text = lines.join("\n")
    const blob = new Blob([text], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${name}-${container || "logs"}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        {containers.length > 1 && (
          <Select value={container} onValueChange={setContainer}>
            <SelectTrigger className="w-[180px] h-8 text-sm">
              <SelectValue placeholder="Container" />
            </SelectTrigger>
            <SelectContent>
              {containers.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Button
          variant={streaming ? "default" : "outline"}
          size="sm"
          className="h-8"
          onClick={() => {
            if (streaming) {
              stopStreaming()
              setFollow(false)
            } else {
              setFollow(true)
            }
          }}
        >
          {streaming ? (
            <>
              <Pause className="h-3.5 w-3.5 mr-1" />
              Stop
            </>
          ) : (
            <>
              <Play className="h-3.5 w-3.5 mr-1" />
              Follow
            </>
          )}
        </Button>

        <Button variant="ghost" size="sm" className="h-8" onClick={clearLogs}>
          <Trash2 className="h-3.5 w-3.5 mr-1" />
          Clear
        </Button>

        <Button variant="ghost" size="sm" className="h-8" onClick={handleDownload}>
          <Download className="h-3.5 w-3.5 mr-1" />
          Download
        </Button>

        <div className="flex-1" />
        <span className="text-xs text-muted-foreground">{lines.length} lines</span>
      </div>

      {/* Log Output */}
      <div
        ref={logRef}
        className="bg-zinc-950 text-zinc-100 rounded-md p-3 font-mono text-xs leading-5 overflow-auto max-h-[600px] min-h-[300px]"
        onScroll={(e) => {
          const el = e.currentTarget
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
          setAutoScroll(atBottom)
        }}
      >
        {loading && lines.length === 0 ? (
          <span className="text-zinc-500">Loading logs...</span>
        ) : error ? (
          <span className="text-red-400">{error}</span>
        ) : lines.length === 0 ? (
          <span className="text-zinc-500">No log output</span>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="hover:bg-zinc-900/50 px-1">
              <span className="text-zinc-600 select-none mr-3">{String(i + 1).padStart(4)}</span>
              {line}
            </div>
          ))
        )}
        {streaming && (
          <div className="flex items-center gap-1 text-green-400 mt-1">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            Streaming...
          </div>
        )}
      </div>
    </div>
  )
}
