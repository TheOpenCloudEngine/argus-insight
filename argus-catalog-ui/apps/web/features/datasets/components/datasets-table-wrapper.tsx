"use client"

import { useState } from "react"
import { Brain } from "lucide-react"

import { Button } from "@workspace/ui/components/button"

import { useDatasets } from "./datasets-provider"
import { DatasetsTable } from "./datasets-table"
import { DatasetsSemanticSearch } from "./datasets-semantic-search"

export function DatasetsTableWrapper() {
  const { datasets, isLoading } = useDatasets()
  const [semanticMode, setSemanticMode] = useState(false)

  if (semanticMode) {
    return (
      <div className="flex flex-1 flex-col gap-4">
        <DatasetsSemanticSearch onClose={() => setSemanticMode(false)} />
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-4">
      <div className="flex justify-end">
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 text-purple-600 border-purple-200 hover:bg-purple-50"
          onClick={() => setSemanticMode(true)}
        >
          <Brain className="h-3.5 w-3.5" />
          Semantic Search
        </Button>
      </div>
      <DatasetsTable data={datasets} isLoading={isLoading} />
    </div>
  )
}
