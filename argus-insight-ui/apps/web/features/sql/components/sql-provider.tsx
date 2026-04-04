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
  activeDatasource: Datasource | null
  setActiveDatasource: (ds: Datasource | null) => void
  refreshDatasources: () => Promise<void>

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

export function SqlProvider({ children }: { children: React.ReactNode }) {
  const [datasources, setDatasources] = useState<Datasource[]>([])
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

  useEffect(() => {
    refreshDatasources()
  }, [refreshDatasources])

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

  const executeCurrentTab = useCallback(async () => {
    const tab = tabs.find((t) => t.id === activeTabId)
    if (!tab || !tab.datasourceId || !tab.sql.trim()) return

    setIsExecuting(true)
    try {
      const result = await api.executeQuery(tab.datasourceId, tab.sql.trim())
      updateTabResult(tab.id, result)
    } catch (e) {
      updateTabResult(tab.id, {
        execution_id: "",
        status: "FAILED",
        columns: [],
        rows: [],
        row_count: 0,
        elapsed_ms: 0,
        error_message: e instanceof Error ? e.message : String(e),
        has_more: false,
      })
    } finally {
      setIsExecuting(false)
    }
  }, [tabs, activeTabId, updateTabResult])

  return (
    <SqlContext.Provider
      value={{
        datasources,
        activeDatasource,
        setActiveDatasource,
        refreshDatasources,
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
