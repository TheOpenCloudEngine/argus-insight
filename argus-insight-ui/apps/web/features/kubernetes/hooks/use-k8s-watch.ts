"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { K8sResourceItem, WatchEvent } from "../types"

/**
 * Hook that connects to an SSE watch endpoint and maintains a live
 * list of K8s resources, applying ADDED/MODIFIED/DELETED events.
 */
export function useK8sWatch(
  resource: string,
  namespace?: string,
  initialItems?: K8sResourceItem[],
) {
  const [items, setItems] = useState<K8sResourceItem[]>(initialItems || [])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    const ns = namespace || "_all"
    const url = `/api/v1/k8s/${encodeURIComponent(ns)}/${resource}/watch`

    // Read token from sessionStorage
    let token = ""
    try {
      const raw = sessionStorage.getItem("argus_tokens")
      if (raw) {
        const tokens = JSON.parse(raw)
        token = tokens.access_token || ""
      }
    } catch {
      // ignore
    }

    const fullUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url
    const es = new EventSource(fullUrl)
    eventSourceRef.current = es

    es.onopen = () => {
      setConnected(true)
      setError(null)
    }

    const handleEvent = (e: MessageEvent) => {
      try {
        const event: WatchEvent = JSON.parse(e.data)
        setItems((prev) => applyWatchEvent(prev, event))
      } catch {
        // ignore parse errors
      }
    }

    es.addEventListener("ADDED", handleEvent)
    es.addEventListener("MODIFIED", handleEvent)
    es.addEventListener("DELETED", handleEvent)

    es.addEventListener("error", (evt) => {
      const errorEvent = evt as MessageEvent
      if (errorEvent.data) {
        try {
          const data = JSON.parse(errorEvent.data)
          setError(data.error || "Watch connection error")
        } catch {
          setError("Watch connection error")
        }
      }
    })

    es.onerror = () => {
      setConnected(false)
      // EventSource will auto-reconnect
    }
  }, [resource, namespace])

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
      setConnected(false)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  // Update items when initialItems changes (e.g., after a fresh fetch)
  useEffect(() => {
    if (initialItems) {
      setItems(initialItems)
    }
  }, [initialItems])

  return { items, connected, error, disconnect, reconnect: connect }
}

function applyWatchEvent(
  items: K8sResourceItem[],
  event: WatchEvent,
): K8sResourceItem[] {
  const uid = event.object?.metadata?.uid
  if (!uid) return items

  switch (event.type) {
    case "ADDED": {
      const exists = items.some((i) => i.metadata.uid === uid)
      if (exists) {
        return items.map((i) => (i.metadata.uid === uid ? event.object : i))
      }
      return [...items, event.object]
    }
    case "MODIFIED":
      return items.map((i) => (i.metadata.uid === uid ? event.object : i))
    case "DELETED":
      return items.filter((i) => i.metadata.uid !== uid)
    default:
      return items
  }
}
