"use client"

import React, { createContext, useCallback, useContext, useEffect, useState } from "react"
import * as api from "../api"
import type { Datasource, EditorTab, QueryResult } from "../types"

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

type SqlDialogType =
  | "add-datasource"
  | "edit-datasource"
  | "save-query"
  | "history"
  | null

interface SqlContextType {
  // Datasources
  datasources: Datasource[]
  workspaceDatasources: Datasource[]
  activeDatasource: Datasource | null
  setActiveDatasource: (ds: Datasource | null) => void
  refreshDatasources: () => Promise<void>
  refreshWorkspaceDatasources: () => Promise<void>

  // Tabs
  tabs: EditorTab[]
  activeTabId: string
  setActiveTabId: (id: string) => void
  addTab: () => void
  closeTab: (id: string) => void
  updateTabSql: (id: string, sql: string) => void
  updateTabDatasource: (id: string, dsId: number | null) => void
  updateTabResult: (id: string, result: QueryResult | null) => void

  // Dialogs
  dialog: SqlDialogType
  setDialog: (d: SqlDialogType) => void

  // Execution
  executeCurrentTab: () => Promise<void>
  executeSql: (sql?: string) => Promise<void>
  cancelExecution: () => Promise<void>
  fetchResultPage: (page: number) => Promise<void>
  isExecuting: boolean
}

const SqlContext = createContext<SqlContextType | null>(null)

let tabCounter = 1

function createTab(): EditorTab {
  const id = `tab-${tabCounter++}`
  return {
    id,
    title: `Query ${tabCounter - 1}`,
    sql: "",
    datasourceId: null,
    result: null,
    status: null,
    executionId: null,
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function SqlProvider({ children, workspaceId }: { children: React.ReactNode; workspaceId?: number }) {
  const [datasources, setDatasources] = useState<Datasource[]>([])
  const [workspaceDatasources, setWorkspaceDatasources] = useState<Datasource[]>([])
  const [activeDatasource, setActiveDatasource] = useState<Datasource | null>(null)
  const [tabs, setTabs] = useState<EditorTab[]>([createTab()])
  const [activeTabId, setActiveTabId] = useState(tabs[0]!.id)
  const [dialog, setDialog] = useState<SqlDialogType>(null)
  const [isExecuting, setIsExecuting] = useState(false)

  const refreshDatasources = useCallback(async () => {
    try {
      const list = await api.fetchDatasources()
      setDatasources(list)
    } catch (e) {
      console.error("Failed to load datasources", e)
    }
  }, [])

  // Fetch workspace DB services as datasources
  const refreshWorkspaceDatasources = useCallback(async () => {
    if (!workspaceId) { setWorkspaceDatasources([]); return }
    try {
      const res = await api.fetchWorkspaceDatasources(workspaceId)
      setWorkspaceDatasources(res)
    } catch {
      setWorkspaceDatasources([])
    }
  }, [workspaceId])

  useEffect(() => {
    refreshDatasources()
    refreshWorkspaceDatasources()
  }, [refreshDatasources, refreshWorkspaceDatasources])

  const addTab = useCallback(() => {
    const tab = createTab()
    // Inherit datasource from active tab
    const activeTab = tabs.find((t) => t.id === activeTabId)
    if (activeTab?.datasourceId) {
      tab.datasourceId = activeTab.datasourceId
    }
    setTabs((prev) => [...prev, tab])
    setActiveTabId(tab.id)
  }, [tabs, activeTabId])

  const closeTab = useCallback(
    (id: string) => {
      setTabs((prev) => {
        const next = prev.filter((t) => t.id !== id)
        if (next.length === 0) {
          const tab = createTab()
          next.push(tab)
        }
        if (activeTabId === id) {
          setActiveTabId(next[next.length - 1]!.id)
        }
        return next
      })
    },
    [activeTabId],
  )

  const updateTabSql = useCallback((id: string, sql: string) => {
    setTabs((prev) => prev.map((t) => (t.id === id ? { ...t, sql } : t)))
  }, [])

  const updateTabDatasource = useCallback((id: string, dsId: number | null) => {
    setTabs((prev) => prev.map((t) => (t.id === id ? { ...t, datasourceId: dsId } : t)))
  }, [])

  const updateTabResult = useCallback((id: string, result: QueryResult | null) => {
    setTabs((prev) =>
      prev.map((t) =>
        t.id === id
          ? { ...t, result, status: result?.status ?? null, executionId: result?.execution_id ?? null }
          : t,
      ),
    )
  }, [])

  const [currentExecutionId, setCurrentExecutionId] = useState<string | null>(null)

  const executeSql = useCallback(async (sqlOverride?: string) => {
    const tab = tabs.find((t) => t.id === activeTabId)
    if (!tab || !tab.datasourceId) return
    const sql = (sqlOverride ?? tab.sql).trim()
    if (!sql) return

    setIsExecuting(true)
    setCurrentExecutionId(null)
    try {
      // Submit query (returns immediately)
      const submitted = await api.submitQuery(tab.datasourceId, sql)
      setCurrentExecutionId(submitted.execution_id)

      // Poll for completion
      const pollInterval = 500
      const maxPolls = 1200 // 10 minutes at 500ms
      for (let i = 0; i < maxPolls; i++) {
        await new Promise((r) => setTimeout(r, pollInterval))
        const status = await api.fetchExecutionStatus(submitted.execution_id)

        if (status.status === "FINISHED") {
          const result = await api.fetchExecutionResult(submitted.execution_id)
          updateTabResult(tab.id, result)
          return
        }
        if (status.status === "FAILED") {
          updateTabResult(tab.id, {
            execution_id: submitted.execution_id,
            status: "FAILED",
            columns: [],
            rows: [],
            row_count: 0,
            elapsed_ms: status.elapsed_ms ?? 0,
            error_message: status.error_message || "Query failed",
            has_more: false,
          })
          return
        }
        if (status.status === "CANCELLED") {
          updateTabResult(tab.id, {
            execution_id: submitted.execution_id,
            status: "CANCELLED",
            columns: [],
            rows: [],
            row_count: 0,
            elapsed_ms: status.elapsed_ms ?? 0,
            error_message: "Query cancelled by user",
            has_more: false,
          })
          return
        }
      }
      // Timeout
      updateTabResult(tab.id, {
        execution_id: submitted.execution_id,
        status: "FAILED",
        columns: [], rows: [], row_count: 0, elapsed_ms: 0,
        error_message: "Polling timeout — query may still be running on the server",
        has_more: false,
      })
    } catch (e) {
      updateTabResult(tab.id, {
        execution_id: "",
        status: "FAILED",
        columns: [], rows: [], row_count: 0, elapsed_ms: 0,
        error_message: e instanceof Error ? e.message : String(e),
        has_more: false,
      })
    } finally {
      setIsExecuting(false)
      setCurrentExecutionId(null)
    }
  }, [tabs, activeTabId, updateTabResult])

  const cancelExecution = useCallback(async () => {
    if (!currentExecutionId) return
    try {
      await api.cancelExecution(currentExecutionId)
    } catch { /* ignore */ }
  }, [currentExecutionId])

  const fetchResultPage = useCallback(async (page: number) => {
    const tab = tabs.find((t) => t.id === activeTabId)
    if (!tab?.result?.execution_id) return
    try {
      const result = await api.fetchExecutionResult(tab.result.execution_id, page)
      updateTabResult(tab.id, result)
    } catch { /* ignore */ }
  }, [tabs, activeTabId, updateTabResult])

  // Keep backward compat
  const executeCurrentTab = useCallback(async () => executeSql(), [executeSql])

  return (
    <SqlContext.Provider
      value={{
        datasources,
        workspaceDatasources,
        activeDatasource,
        setActiveDatasource,
        refreshDatasources,
        refreshWorkspaceDatasources,
        tabs,
        activeTabId,
        setActiveTabId,
        addTab,
        closeTab,
        updateTabSql,
        updateTabDatasource,
        updateTabResult,
        dialog,
        setDialog,
        executeCurrentTab,
        executeSql,
        cancelExecution,
        fetchResultPage,
        isExecuting,
      }}
    >
      {children}
    </SqlContext.Provider>
  )
}

export function useSql() {
  const ctx = useContext(SqlContext)
  if (!ctx) throw new Error("useSql must be used within SqlProvider")
  return ctx
}
