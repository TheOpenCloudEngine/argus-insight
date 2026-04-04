"use client"

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react"
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
  updateTabTitle: (id: string, title: string) => void
  updateTabDatasource: (id: string, dsId: number | null) => void
  updateTabResult: (id: string, result: QueryResult | null) => void

  // Save
  saveTabs: () => Promise<void>
  saveToast: string | null

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
  const id = crypto.randomUUID()
  const title = `Query ${tabCounter++}`
  return {
    id,
    title,
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
  const [saveToast, setSaveToast] = useState<string | null>(null)
  const tabsLoadedRef = useRef(false)

  // Get current user ID from sessionStorage token
  const getUserId = useCallback((): number => {
    try {
      const tokens = localStorage.getItem("argus_tokens")
      if (tokens) {
        const parsed = JSON.parse(tokens)
        const payload = JSON.parse(atob(parsed.access_token.split(".")[1]))
        return parseInt(payload.sub, 10) || 0
      }
    } catch { /* ignore */ }
    return 0
  }, [])

  const refreshDatasources = useCallback(async () => {
    try {
      const list = await api.fetchDatasources()
      setDatasources(list)
    } catch (e) {
      console.error("Failed to load datasources", e)
    }
  }, [])

  const refreshWorkspaceDatasources = useCallback(async () => {
    if (!workspaceId) { setWorkspaceDatasources([]); return }
    try {
      const res = await api.fetchWorkspaceDatasources(workspaceId)
      setWorkspaceDatasources(res)
    } catch {
      setWorkspaceDatasources([])
    }
  }, [workspaceId])

  // Load tabs from DB on mount
  useEffect(() => {
    refreshDatasources()
    refreshWorkspaceDatasources()

    if (!workspaceId || tabsLoadedRef.current) return
    const userId = getUserId()
    if (!userId) return

    api.loadTabs(workspaceId, userId).then((saved) => {
      if (saved.length > 0) {
        tabCounter = saved.length + 1
        const loaded: EditorTab[] = saved.map((t) => ({
          id: t.id,
          title: t.title,
          sql: t.sql_text,
          datasourceId: t.datasource_id,
          result: null,
          status: null,
          executionId: null,
        }))
        setTabs(loaded)
        setActiveTabId(loaded[0]!.id)
      }
      tabsLoadedRef.current = true
    }).catch(() => { tabsLoadedRef.current = true })
  }, [refreshDatasources, refreshWorkspaceDatasources, workspaceId, getUserId])

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

  const updateTabTitle = useCallback((id: string, title: string) => {
    setTabs((prev) => prev.map((t) => (t.id === id ? { ...t, title } : t)))
  }, [])

  const updateTabDatasource = useCallback((id: string, dsId: number | null) => {
    setTabs((prev) => prev.map((t) => (t.id === id ? { ...t, datasourceId: dsId } : t)))
  }, [])

  // Save all tabs to DB
  const saveTabs = useCallback(async () => {
    if (!workspaceId) return
    const userId = getUserId()
    if (!userId) return
    try {
      await api.saveTabs(workspaceId, userId, tabs.map((t, i) => ({
        id: t.id,
        title: t.title,
        sql_text: t.sql,
        datasource_id: t.datasourceId,
        tab_order: i,
      })))
      setSaveToast("Saved")
      setTimeout(() => setSaveToast(null), 2000)
    } catch {
      setSaveToast("Failed to save")
      setTimeout(() => setSaveToast(null), 3000)
    }
  }, [workspaceId, getUserId, tabs])

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
        updateTabTitle,
        saveTabs,
        saveToast,
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
