"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  AlertTriangle,
  ArrowDown,
  Copy,
  Download,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Search,
  Terminal,
  X,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import type {
  ContainerInfo,
  ServiceEvent,
  ServiceLogSources,
  WorkspaceService,
} from "@/features/workspaces/types"
import {
  createServiceLogStream,
  fetchServiceEvents,
  fetchServiceLogSources,
  fetchServiceLogs,
} from "@/features/workspaces/api"

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TAIL_OPTIONS = [
  { value: "50", label: "50 lines" },
  { value: "100", label: "100 lines" },
  { value: "500", label: "500 lines" },
  { value: "1000", label: "1,000 lines" },
  { value: "5000", label: "5,000 lines" },
]

const SINCE_OPTIONS = [
  { value: "all", label: "All time" },
  { value: "300", label: "Last 5m" },
  { value: "1800", label: "Last 30m" },
  { value: "3600", label: "Last 1h" },
  { value: "21600", label: "Last 6h" },
  { value: "86400", label: "Last 24h" },
]

// ---------------------------------------------------------------------------
// Log level parsing
// ---------------------------------------------------------------------------

type LogLevel = "error" | "warn" | "info" | "debug" | "trace" | "unknown"

function parseLogLevel(line: string): LogLevel {
  // Skip timestamp prefix to find level keyword
  const upper = line.toUpperCase()
  if (upper.includes("ERROR") || upper.includes("FATAL") || upper.includes("CRITICAL"))
    return "error"
  if (upper.includes("WARN")) return "warn"
  if (upper.includes("DEBUG")) return "debug"
  if (upper.includes("TRACE")) return "trace"
  if (upper.includes("INFO")) return "info"
  return "unknown"
}

const LEVEL_COLORS: Record<LogLevel, string> = {
  error: "text-red-500 dark:text-red-400",
  warn: "text-yellow-600 dark:text-yellow-400",
  info: "",
  debug: "text-muted-foreground",
  trace: "text-muted-foreground/60",
  unknown: "",
}

// ---------------------------------------------------------------------------
// Container tab
// ---------------------------------------------------------------------------

function ContainerTab({
  container,
  selected,
  onClick,
}: {
  container: ContainerInfo
  selected: boolean
  onClick: () => void
}) {
  const stateColor =
    container.state === "running"
      ? "bg-green-500"
      : container.state === "terminated"
        ? "bg-gray-400"
        : container.state === "waiting"
          ? "bg-yellow-500"
          : "bg-gray-300"

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors ${
        selected
          ? "bg-primary text-primary-foreground"
          : "hover:bg-muted text-muted-foreground"
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${stateColor}`} />
      <span>{container.label}</span>
      {container.restart_count > 0 && (
        <Badge variant="outline" className="ml-1 h-4 px-1 text-[10px]">
          {container.restart_count}x
        </Badge>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Events panel
// ---------------------------------------------------------------------------

function EventsPanel({ events }: { events: ServiceEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="text-muted-foreground py-4 text-center text-sm">
        No events found for this service.
      </p>
    )
  }
  return (
    <div className="space-y-2">
      {events.map((ev, i) => (
        <div
          key={`${ev.reason}-${i}`}
          className={`flex items-start gap-3 rounded-md border p-3 text-sm ${
            ev.type === "Warning"
              ? "border-yellow-500/30 bg-yellow-500/5"
              : "border-border"
          }`}
        >
          {ev.type === "Warning" && (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{ev.reason}</span>
              {ev.count > 1 && (
                <Badge variant="secondary" className="h-4 px-1 text-[10px]">
                  x{ev.count}
                </Badge>
              )}
              {ev.last_timestamp && (
                <span className="text-muted-foreground text-xs">
                  {new Date(ev.last_timestamp).toLocaleTimeString()}
                </span>
              )}
            </div>
            <p className="text-muted-foreground mt-0.5">{ev.message}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ServiceLogsPanelProps {
  workspaceId: number
  service: WorkspaceService
}

export function ServiceLogsPanel({ workspaceId, service }: ServiceLogsPanelProps) {
  // State
  const [logSources, setLogSources] = useState<ServiceLogSources | null>(null)
  const [selectedContainer, setSelectedContainer] = useState<string>("")
  const [lines, setLines] = useState<string[]>([])
  const [events, setEvents] = useState<ServiceEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [tailLines, setTailLines] = useState("100")
  const [sinceSeconds, setSinceSeconds] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [showEvents, setShowEvents] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)

  const logRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  // When true, onScroll won't auto-enable autoScroll even if at bottom.
  // Set by explicit user toggle-OFF, cleared only by user scrolling away and back.
  const userDisabledRef = useRef(false)

  // Load log sources on mount
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([
      fetchServiceLogSources(workspaceId, service.id),
      fetchServiceEvents(workspaceId, service.id),
    ])
      .then(([sources, evts]) => {
        if (cancelled) return
        setLogSources(sources)
        setEvents(evts)
        // Auto-select first running container, or first container
        const running = sources.containers.find((c) => c.state === "running")
        setSelectedContainer(running?.name ?? sources.containers[0]?.name ?? "")
      })
      .catch((e) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [workspaceId, service.id])

  // Fetch logs when container/filter changes
  const fetchLogs = useCallback(async () => {
    if (!selectedContainer) return
    setLoading(true)
    setError(null)
    try {
      const data = await fetchServiceLogs(workspaceId, service.id, {
        container: selectedContainer,
        tailLines: parseInt(tailLines),
        sinceSeconds: sinceSeconds !== "all" ? parseInt(sinceSeconds) : undefined,
      })
      setLines(data.lines)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [workspaceId, service.id, selectedContainer, tailLines, sinceSeconds])

  useEffect(() => {
    if (selectedContainer && !streaming) {
      fetchLogs()
    }
  }, [selectedContainer, tailLines, sinceSeconds, fetchLogs, streaming])

  // Auto-scroll to bottom when new lines arrive
  useEffect(() => {
    if (autoScroll && logRef.current) {
      // Wait for DOM to paint the new rows before scrolling
      requestAnimationFrame(() => {
        if (logRef.current) {
          logRef.current.scrollTop = logRef.current.scrollHeight
        }
      })
    }
  }, [lines, autoScroll])

  // Toggle auto-scroll via button click
  const handleAutoScrollToggle = useCallback(() => {
    const next = !autoScroll
    setAutoScroll(next)
    if (next) {
      // Turning ON: scroll to bottom immediately, clear disabled flag
      userDisabledRef.current = false
      requestAnimationFrame(() => {
        if (logRef.current) {
          logRef.current.scrollTop = logRef.current.scrollHeight
        }
      })
    } else {
      // Turning OFF: prevent onScroll from re-enabling
      userDisabledRef.current = true
    }
  }, [autoScroll])

  // Toggle streaming
  const toggleStreaming = useCallback(() => {
    if (streaming) {
      // Stop streaming
      eventSourceRef.current?.close()
      eventSourceRef.current = null
      setStreaming(false)
    } else {
      // Start streaming
      setStreaming(true)
      const es = createServiceLogStream(workspaceId, service.id, {
        container: selectedContainer || undefined,
        tailLines: parseInt(tailLines),
        sinceSeconds: sinceSeconds !== "all" ? parseInt(sinceSeconds) : undefined,
      })
      eventSourceRef.current = es

      // Clear existing lines when starting stream
      setLines([])

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.line) {
            setLines((prev) => [...prev, data.line])
          }
        } catch {
          // ignore parse errors
        }
      }
      es.onerror = () => {
        es.close()
        eventSourceRef.current = null
        setStreaming(false)
      }
    }
  }, [streaming, workspaceId, service.id, selectedContainer, tailLines, sinceSeconds])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  // Copy logs to clipboard
  const copyLogs = useCallback(() => {
    const text = filteredLines.join("\n")
    navigator.clipboard.writeText(text)
  }, [lines, searchQuery])

  // Download logs
  const downloadLogs = useCallback(() => {
    const text = lines.join("\n")
    const blob = new Blob([text], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${service.plugin_name}-${selectedContainer}-logs.txt`
    a.click()
    URL.revokeObjectURL(url)
  }, [lines, service.plugin_name, selectedContainer])

  // Filter lines by search
  const filteredLines = searchQuery
    ? lines.filter((l) => l.toLowerCase().includes(searchQuery.toLowerCase()))
    : lines

  const allContainers = [
    ...(logSources?.containers ?? []),
    ...(logSources?.init_containers ?? []),
  ]

  // ---------- Render ----------

  if (error && !logSources) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <AlertTriangle className="text-muted-foreground mx-auto mb-2 h-8 w-8" />
          <p className="text-sm text-red-500">{error}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={fetchLogs}>
            <RefreshCw className="mr-1 h-3 w-3" /> Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="flex h-[600px] flex-col">
      <CardHeader className="flex-none space-y-3 pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Terminal className="h-4 w-4" />
            Service Logs
            {logSources && (
              <Badge variant="outline" className="font-mono text-xs">
                {logSources.pod_name}
              </Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={showEvents ? "secondary" : "ghost"}
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setShowEvents(!showEvents)}
                >
                  <AlertTriangle className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>K8s Events</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={copyLogs}
                >
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Copy logs</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={downloadLogs}
                >
                  <Download className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Download logs</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Container tabs */}
        {allContainers.length > 1 && (
          <div className="bg-muted/50 flex flex-wrap gap-1 rounded-lg p-1">
            {allContainers.map((c) => (
              <ContainerTab
                key={c.name}
                container={c}
                selected={c.name === selectedContainer}
                onClick={() => {
                  if (streaming) {
                    eventSourceRef.current?.close()
                    eventSourceRef.current = null
                    setStreaming(false)
                  }
                  setSelectedContainer(c.name)
                }}
              />
            ))}
          </div>
        )}

        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          <Select value={tailLines} onValueChange={setTailLines}>
            <SelectTrigger className="h-7 w-[120px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TAIL_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={sinceSeconds} onValueChange={setSinceSeconds}>
            <SelectTrigger className="h-7 w-[110px] text-xs">
              <SelectValue placeholder="Time range" />
            </SelectTrigger>
            <SelectContent>
              {SINCE_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="relative flex-1">
            <Search className="text-muted-foreground absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2" />
            <Input
              placeholder="Filter logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-7 pl-7 text-xs"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="text-muted-foreground absolute right-2 top-1/2 -translate-y-1/2"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={streaming ? "destructive" : "outline"}
                size="sm"
                className="h-7 gap-1 text-xs"
                onClick={toggleStreaming}
              >
                {streaming ? (
                  <>
                    <Pause className="h-3 w-3" /> Stop
                  </>
                ) : (
                  <>
                    <Play className="h-3 w-3" /> Stream
                  </>
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {streaming ? "Stop live streaming" : "Start live log streaming"}
            </TooltipContent>
          </Tooltip>

          {!streaming && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7"
                  onClick={fetchLogs}
                  disabled={loading}
                >
                  <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Refresh</TooltipContent>
            </Tooltip>
          )}

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={autoScroll ? "secondary" : "ghost"}
                size="icon"
                className="h-7 w-7"
                onClick={handleAutoScrollToggle}
              >
                <ArrowDown className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
            </TooltipContent>
          </Tooltip>
        </div>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col overflow-hidden p-0">
        {showEvents ? (
          <div className="flex-1 overflow-auto p-4">
            <EventsPanel events={events} />
          </div>
        ) : (
          <div
            ref={logRef}
            className="bg-muted/30 min-h-0 flex-1 overflow-auto font-mono text-xs leading-5"
            onScroll={(e) => {
              const el = e.currentTarget
              const atBottom =
                el.scrollHeight - el.scrollTop - el.clientHeight < 40

              if (atBottom) {
                // At bottom: re-enable only if user didn't explicitly disable
                if (!userDisabledRef.current && !autoScroll) {
                  setAutoScroll(true)
                }
              } else {
                // Scrolled up: disable auto-scroll, clear the user-disabled flag
                // so that scrolling back to bottom re-enables it naturally
                userDisabledRef.current = false
                if (autoScroll) setAutoScroll(false)
              }
            }}
          >
            {loading && lines.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
              </div>
            ) : filteredLines.length === 0 ? (
              <div className="text-muted-foreground flex h-full items-center justify-center">
                {searchQuery ? "No matching log lines." : "No logs available."}
              </div>
            ) : (
              <table className="w-full border-collapse">
                <tbody>
                  {filteredLines.map((line, i) => {
                    const level = parseLogLevel(line)
                    return (
                      <tr
                        key={i}
                        className="hover:bg-muted/50 group border-b border-transparent"
                      >
                        <td className="text-muted-foreground/50 w-[1%] select-none whitespace-nowrap px-3 py-0 text-right align-top">
                          {i + 1}
                        </td>
                        <td
                          className={`whitespace-pre-wrap break-all px-2 py-0 ${LEVEL_COLORS[level]}`}
                        >
                          {line}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Status bar */}
        <div className="bg-muted/50 flex shrink-0 items-center justify-between border-t px-3 py-1 text-[10px] text-muted-foreground">
          <span>
            {filteredLines.length} line{filteredLines.length !== 1 ? "s" : ""}
            {searchQuery &&
              ` (filtered from ${lines.length})`}
          </span>
          <span className="flex items-center gap-2">
            {streaming && (
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
                Live
              </span>
            )}
            {selectedContainer && (
              <span>container: {selectedContainer}</span>
            )}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
