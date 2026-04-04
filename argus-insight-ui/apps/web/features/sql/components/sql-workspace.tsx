"use client"

import React from "react"
import { TooltipProvider } from "@workspace/ui/components/tooltip"
import { DatasourceDialog } from "./datasource-dialog"
import { DatasourceSidebar } from "./datasource-sidebar"
import { ResultPanel } from "./result-panel"
import { SaveQueryDialog } from "./save-query-dialog"
import { SqlEditorPanel } from "./sql-editor-panel"

export function SqlWorkspace() {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-full min-h-0 flex-1">
        {/* Left: Datasource tree (fixed width) */}
        <div className="w-64 shrink-0 overflow-hidden">
          <DatasourceSidebar />
        </div>

        {/* Right: Editor + Results (vertical split) */}
        <div className="flex flex-1 flex-col min-w-0">
          {/* Top: SQL Editor */}
          <div className="flex-1 min-h-[200px] border-b overflow-hidden">
            <SqlEditorPanel />
          </div>

          {/* Bottom: Results */}
          <div className="h-[45%] min-h-[150px] overflow-hidden">
            <ResultPanel />
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <DatasourceDialog />
      <SaveQueryDialog />
    </TooltipProvider>
  )
}
