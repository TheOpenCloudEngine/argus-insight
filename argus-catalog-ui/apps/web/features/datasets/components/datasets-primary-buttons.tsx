"use client"

import { Plus } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { useDatasets } from "./datasets-provider"

export function DatasetsPrimaryButtons() {
  const { setOpen } = useDatasets()

  return (
    <Button size="sm" onClick={() => setOpen("add")}>
      <Plus className="mr-1 h-4 w-4" />
      Add Dataset
    </Button>
  )
}
