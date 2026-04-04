"use client"

import React, { useCallback, useEffect, useRef, useState } from "react"
import {
  Loader2,
  Play,
  Plus,
  Save,
  X,
} from "lucide-react"
import Editor, { type OnMount } from "@monaco-editor/react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { Button } from "@workspace/ui/components/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@workspace/ui/components/tooltip"
import * as api from "../api"
import type { AutocompleteData } from "../types"
import { useSql } from "./sql-provider"

// ---------------------------------------------------------------------------
// SQL Editor Panel (tabs + Monaco editor + toolbar)
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
    executeSql,
    isExecuting,
    setDialog,
    workspaceDatasources,
    updateTabDatasource,
  } = useSql()

  const activeTab = tabs.find((t) => t.id === activeTabId)
  const editorRef = useRef<any>(null)
  const executeRef = useRef<() => void>(() => {})
  const [alertMsg, setAlertMsg] = useState("")

  // Determine engine type for syntax hints
  const activeDsId = activeTab?.datasourceId
  const allDatasources = workspaceDatasources
  const activeDs = allDatasources.find((ds) => ds.id === activeDsId)

  // Map engine type → Monaco language for syntax highlighting
  const ENGINE_LANG: Record<string, string> = {
    postgresql: "pgsql",
    mariadb: "mysql",
    starrocks: "mysql",
    trino: "sql",
  }
  const editorLanguage = activeDs ? (ENGINE_LANG[activeDs.engine_type] ?? "sql") : "sql"

  // Execute selection or full SQL
  const executeSelectionOrAll = useCallback(() => {
    if (!activeTab?.datasourceId) {
      setAlertMsg("Please select a DataSource first.")
      return
    }
    const editor = editorRef.current
    if (!editor) { executeSql(); return }
    const selection = editor.getSelection()
    if (selection && !selection.isEmpty()) {
      const selectedText = editor.getModel()?.getValueInRange(selection) ?? ""
      if (selectedText.trim()) {
        executeSql(selectedText)
        return
      }
    }
    executeSql()
  }, [executeSql, activeTab?.datasourceId])

  // Keep ref always pointing to latest function (avoids stale closure in Monaco action)
  executeRef.current = executeSelectionOrAll

  // Autocomplete: fetch metadata when datasource changes
  const autocompleteRef = useRef<AutocompleteData | null>(null)
  const completionDisposableRef = useRef<any>(null)

  useEffect(() => {
    if (!activeDsId) { autocompleteRef.current = null; return }
    let cancelled = false
    api.fetchAutocomplete(activeDsId).then((data) => {
      if (!cancelled) autocompleteRef.current = data
    }).catch(() => {})
    return () => { cancelled = true }
  }, [activeDsId])

  // Monaco mount handler — register Ctrl+Enter shortcut + completion provider
  const handleEditorMount: OnMount = useCallback(
    (editor, monaco) => {
      editorRef.current = editor
      editor.addAction({
        id: "execute-query",
        label: "Execute Query (Selection or All)",
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
        run: () => executeRef.current(),
      })

      // Register completion provider for all SQL languages
      const languages = ["sql", "pgsql", "mysql"]
      for (const lang of languages) {
        const disposable = monaco.languages.registerCompletionItemProvider(lang, {
          triggerCharacters: [".", " "],
          provideCompletionItems: (model, position) => {
            const ac = autocompleteRef.current
            if (!ac) return { suggestions: [] }

            const word = model.getWordUntilPosition(position)
            const range = {
              startLineNumber: position.lineNumber,
              endLineNumber: position.lineNumber,
              startColumn: word.startColumn,
              endColumn: word.endColumn,
            }

            const suggestions: any[] = []

            // Schemas
            for (const s of ac.schemas) {
              suggestions.push({
                label: s,
                kind: monaco.languages.CompletionItemKind.Module,
                insertText: s,
                detail: "schema",
                range,
              })
            }

            // Tables
            for (const t of ac.tables) {
              suggestions.push({
                label: t,
                kind: monaco.languages.CompletionItemKind.Struct,
                insertText: t,
                detail: "table",
                range,
              })
            }

            // Columns
            for (const c of ac.columns) {
              suggestions.push({
                label: c,
                kind: monaco.languages.CompletionItemKind.Field,
                insertText: c,
                detail: "column",
                range,
              })
            }

            // Keywords
            for (const k of ac.keywords) {
              suggestions.push({
                label: k,
                kind: monaco.languages.CompletionItemKind.Keyword,
                insertText: k,
                range,
              })
            }

            // Functions
            for (const f of ac.functions) {
              suggestions.push({
                label: f,
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: f + "()",
                detail: "function",
                range,
              })
            }

            return { suggestions }
          },
        })
        if (!completionDisposableRef.current) completionDisposableRef.current = []
        completionDisposableRef.current.push(disposable)
      }
    },
    [],
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
        {/* Datasource selector — grouped */}
        <select
          className="h-7 rounded-md border bg-background px-2 text-sm"
          value={activeTab?.datasourceId ?? ""}
          onChange={(e) => {
            const val = e.target.value ? Number(e.target.value) : null
            updateTabDatasource(activeTabId, val)
          }}
        >
          <option value="">Select Datasource...</option>
          {workspaceDatasources.map((ds) => (
            <option key={`ws-${ds.id}`} value={ds.id}>
              {ds.name} ({ds.engine_type})
            </option>
          ))}
        </select>

        {activeDs && (
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground uppercase">
            {activeDs.engine_type}
          </span>
        )}

        <div className="flex-1" />

        {/* Execute */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="default"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={executeSelectionOrAll}
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

      {/* Monaco Editor */}
      <div className="flex-1 min-h-0 min-w-0 overflow-hidden">
        <Editor
          height="100%"
          language={editorLanguage}
          value={activeTab?.sql ?? ""}
          onChange={(value) => updateTabSql(activeTabId, value ?? "")}
          onMount={handleEditorMount}
          options={{
            fontFamily: "'D2Coding', 'D2 Coding', monospace",
            fontSize: 14,
            lineNumbers: "on",
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            wordWrap: "on",
            suggestOnTriggerCharacters: true,
            quickSuggestions: true,
            padding: { top: 8 },
            renderWhitespace: "none",
            overviewRulerLanes: 0,
            hideCursorInOverviewRuler: true,
            scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
          }}
          theme="light"
        />
      </div>

      <AlertDialog open={!!alertMsg} onOpenChange={(open) => { if (!open) setAlertMsg("") }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Notice</AlertDialogTitle>
            <AlertDialogDescription>{alertMsg}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setAlertMsg("")}>OK</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
