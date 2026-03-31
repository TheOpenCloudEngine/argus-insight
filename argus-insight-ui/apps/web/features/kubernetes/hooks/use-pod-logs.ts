"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { fetchPodLogs } from "../api"

/**
 * Hook for fetching and streaming pod logs.
 */
export function usePodLogs(
  name: string,
  namespace: string,
  options?: {
    container?: string
    tailLines?: number
    follow?: boolean
  },
) {
  const [lines, setLines] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchPodLogs(name, namespace, {
        container: options?.container,
        tailLines: options?.tailLines ?? 200,
      })
      setLines(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [name, namespace, options?.container, options?.tailLines])

  const startStreaming = useCallback(() => {
    const params = new URLSearchParams({
      follow: "true",
      tailLines: String(options?.tailLines ?? 200),
      timestamps: "true",
    })
    if (options?.container) params.set("container", options.container)

    const url = `/api/v1/k8s/${encodeURIComponent(namespace)}/pods/${encodeURIComponent(name)}/logs?${params.toString()}`
    const es = new EventSource(url)
    eventSourceRef.current = es
    setStreaming(true)

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.line) {
          setLines((prev) => [...prev, data.line])
        }
      } catch {
        // ignore
      }
    }

    es.addEventListener("error", (evt) => {
      const errorEvent = evt as MessageEvent
      if (errorEvent.data) {
        try {
          const data = JSON.parse(errorEvent.data)
          setError(data.error)
        } catch {
          // ignore
        }
      }
      setStreaming(false)
    })

    es.onerror = () => {
      setStreaming(false)
    }
  }, [name, namespace, options?.container, options?.tailLines])

  const stopStreaming = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
      setStreaming(false)
    }
  }, [])

  useEffect(() => {
    if (options?.follow) {
      startStreaming()
    } else {
      fetchLogs()
    }
    return () => stopStreaming()
  }, [options?.follow, fetchLogs, startStreaming, stopStreaming])

  const clearLogs = useCallback(() => setLines([]), [])

  return { lines, loading, error, streaming, fetchLogs, startStreaming, stopStreaming, clearLogs }
}
