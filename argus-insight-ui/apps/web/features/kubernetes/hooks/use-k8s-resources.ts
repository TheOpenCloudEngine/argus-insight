"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "../api"
import type { ClusterOverview, K8sResourceItem, K8sResourceList } from "../types"

/**
 * Hook to fetch and auto-refresh a K8s resource list.
 */
export function useK8sResources(
  resource: string,
  namespace?: string,
  refreshInterval = 10000,
) {
  const [data, setData] = useState<K8sResourceList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval>>()

  const fetchData = useCallback(async () => {
    try {
      const result = await api.listResources(resource, namespace)
      setData(result)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [resource, namespace])

  useEffect(() => {
    setLoading(true)
    fetchData()
    intervalRef.current = setInterval(fetchData, refreshInterval)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchData, refreshInterval])

  return { data, loading, error, refetch: fetchData }
}

/**
 * Hook to fetch a single K8s resource.
 */
export function useK8sResource(
  resource: string,
  name: string,
  namespace?: string,
) {
  const [data, setData] = useState<K8sResourceItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const result = await api.getResource(resource, name, namespace)
      setData(result)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [resource, name, namespace])

  useEffect(() => {
    setLoading(true)
    fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}

/**
 * Hook to fetch the cluster overview.
 */
export function useClusterOverview(refreshInterval = 15000) {
  const [data, setData] = useState<ClusterOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval>>()

  const fetchData = useCallback(async () => {
    try {
      const result = await api.fetchClusterOverview()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    intervalRef.current = setInterval(fetchData, refreshInterval)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchData, refreshInterval])

  return { data, loading, error, refetch: fetchData }
}

/**
 * Hook to fetch namespace list.
 */
export function useNamespaces() {
  const [namespaces, setNamespaces] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.fetchNamespaces()
      .then((ns) => setNamespaces(ns))
      .catch(() => setNamespaces([]))
      .finally(() => setLoading(false))
  }, [])

  return { namespaces, loading }
}
