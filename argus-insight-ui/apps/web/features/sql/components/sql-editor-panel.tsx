"use client"

import React, { useCallback, useRef } from "react"
import {
  Loader2,
  Play,
  Plus,
  Save,
  Square,
  X,
} from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@workspace/ui/components/tooltip"
import { useSql } from "./sql-provider"

// ---------------------------------------------------------------------------
// SQL Editor Panel (tabs + textarea + toolbar + results)
// ---------------------------------------------------------------------------

export function SqlEditorPanel() {
  const {
    tabs,
    activeTabId,
    setActiveTabId,
    addTab,
    closeTab,
    updateTabSql,
    executeCurrentTab,
    isExecuting,
    setDialog,
    datasources,
    updateTabDatasource,
  } = useSql()

  const activeTab = tabs.find((t) => t.id === activeTabId)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Ctrl+Enter or Cmd+Enter to execute
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault()
        executeCurrentTab()
      }
      // Tab key → insert 2 spaces
      if (e.key === "Tab") {
        e.preventDefault()
        const ta = e.currentTarget
        const start = ta.selectionStart
        const end = ta.selectionEnd
        const value = ta.value
        const newVal = value.substring(0, start) + "  " + value.substring(end)
        updateTabSql(activeTabId, newVal)
        // Restore cursor position
        requestAnimationFrame(() => {
          ta.selectionStart = ta.selectionEnd = start + 2
        })
      }
    },
    [activeTabId, executeCurrentTab, updateTabSql],
  )

  return (
    <div className="flex h-full flex-col">
      {/* Tab bar */}
      <div className="flex items-center border-b bg-muted/30">
        <div className="flex flex-1 items-center overflow-x-auto">
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className={`group flex items-center gap-1 border-r px-3 py-1.5 text-xs cursor-pointer hover:bg-muted/50 ${
                tab.id === activeTabId
                  ? "bg-background text-foreground border-b-2 border-b-primary"
                  : "text-muted-foreground"
              }`}
              onClick={() => setActiveTabId(tab.id)}
            >
              <span className="truncate max-w-[120px]">{tab.title}</span>
              {tabs.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    closeTab(tab.id)
                  }}
                  className="ml-1 rounded p-0.5 opacity-0 group-hover:opacity-100 hover:bg-muted"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          ))}
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7 mx-1" onClick={addTab}>
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>New Tab</TooltipContent>
        </Tooltip>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b px-3 py-1.5">
        {/* Datasource selector */}
        <select
          className="h-7 rounded-md border bg-background px-2 text-xs"
          value={activeTab?.datasourceId ?? ""}
          onChange={(e) => {
            const val = e.target.value ? Number(e.target.value) : null
            updateTabDatasource(activeTabId, val)
          }}
        >
          <option value="">Select Datasource...</option>
          {datasources.map((ds) => (
            <option key={ds.id} value={ds.id}>
              {ds.name} ({ds.engine_type})
            </option>
          ))}
        </select>

        <div className="flex-1" />

        {/* Execute */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="default"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={executeCurrentTab}
              disabled={isExecuting || !activeTab?.datasourceId || !activeTab?.sql.trim()}
            >
              {isExecuting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              Run
            </Button>
          </TooltipTrigger>
          <TooltipContent>Execute (Ctrl+Enter)</TooltipContent>
        </Tooltip>

        {/* Save */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={() => setDialog("save-query")}
              disabled={!activeTab?.sql.trim()}
            >
              <Save className="h-3.5 w-3.5" />
              Save
            </Button>
          </TooltipTrigger>
          <TooltipContent>Save Query</TooltipContent>
        </Tooltip>
      </div>

      {/* Editor area */}
      <div className="flex-1 min-h-0">
        <textarea
          ref={textareaRef}
          className="h-full w-full resize-none bg-background p-3 font-mono text-sm leading-relaxed outline-none"
          placeholder="-- Write your SQL query here..."
          value={activeTab?.sql ?? ""}
          onChange={(e) => updateTabSql(activeTabId, e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
        />
      </div>
    </div>
  )
}
